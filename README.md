# ATM 钞箱装载与吐钞优化器

给定一串按顺序发生的提款请求，联合决定：

1. 每个钞箱使用哪种候选面额（2–6 个钞箱，允许不同钞箱使用相同面额）；
2. 每个钞箱初始装入多少张（受单箱容量、整机总张数上限、初装资金上限约束）；
3. 每一笔提款具体从哪些钞箱各吐多少张（精确凑额，成功后立即扣减库存）。

纯 Python 3.12 标准库实现，不接真实账户、银行卡或 ATM 硬件。

## 目标顺序（严格字典序，禁止加权和）

方案按以下 4 元组做严格字典序最小化，前一层相等才比较下一层：

1. `penalty_total`：未满足提款的业务罚值之和；
2. `transport_reload_cost`：运钞与补货成本 =
   `transport_cost_per_note * 初始总张数 + load_cost_per_cassette * 实际使用钞箱数`
   （实际使用 = 初装张数 > 0 的钞箱数）；
3. `initial_cash_used`：初装现金占用 = `sum(面额[i] * 初装张数[i])`；
4. `dispensed_notes`：成功提款吐出的总张数。

四层目标完全相同时，再依次比较三个向量并取字典序最小：
`denomination_vector`（0 表示该钞箱不使用，排在最前）→ `initial_counts_vector`
→ 整段序列的吐钞向量（逐笔连接；失败动作记为 `null`，规范化时排在任何吐钞元组之前）。
面额候选输入顺序、去重、内部遍历顺序均不影响结果；JSON 按键排序、固定格式，
最优值与输出逐字节确定。

## 状态表示

- **装载配置**（loading）：`(faces, counts)`，`faces` 非降序（含 0 哨兵），
  `counts` 为初装张数；空钞箱张数必为 0。
- **序列搜索状态**（固定装载后，第 t 层）：
  `(stock, prefix, penalty, notes)`：当前各钞箱剩余张数、已发生动作前缀
  （每笔一个吐钞向量或失败 `null`）、累计罚值、累计吐钞张数。
- 每笔请求的转移：按字典序枚举所有精确凑额向量（成功，扣减库存），
  再追加一个失败动作（库存不变、加罚值）。

## 支配关系与剪枝安全边界

同一层中，状态 A **支配** B 当且仅当：

- `stock_A[i] >= stock_B[i]`（每个钞箱都不少券），
- `penalty_A <= penalty_B`，`notes_A <= notes_B`。

此时从 B 出发可行的任意未来动作序列，从 A 出发同样可行（面额相同、
库存逐分量不少），未来罚值相同、未来吐钞张数不会更多，因此 B 不可能产生
更优的四层目标。若 stock/penalty/notes 完全相同，则保留规范吐钞前缀更小的
唯一代表。被剪状态必须在同层存在满足上述全部不等式的支配者——该边界可直接
逐条校验，不会漏掉任何可能产生最优解的状态。测试中的 oracle 会同时关闭
装载级分支定界（`planner.BRANCH_AND_BOUND=False`）与状态支配剪枝
（`sequence.DOMINANCE_PRUNING=False`）做全枚举对照。

装载枚举按 `(faces, counts)` 字典序流式生成；一旦首层罚值被证明达到松弛
下界，即对部分成本/现金已不可能优于当前最好方案的装载前缀做分支定界剪枝
（成本与现金随后续钞箱只增不减，故剪枝安全）。

## 搜索预算与未完成结果

`search_budget` 为正整数时，限定“生成的搜索状态数”上限。预算耗尽立即停止，
返回 `status="incomplete"`、`optimal=false`，并给出：

- `upper_bound`：当前最好完整方案的 4 层目标（无完整方案时为充分大整数）；
- `lower_bound`：由松弛证明的下界——第 1 层用“至多 total_note_limit 张候选
  钞票可达金额”的计数找零 DP（放松单箱容量、面额分组与序列耦合），
  连该松弛都无法凑出的金额必然失败，其罚值求和为可证罚值下界；
  第 2–4 层取 0（普遍合法的分量下界）；
- `explored_states`：实际已探索状态数。

未证明最优时一定显式标 `optimal=false`，当前方案绝不冒充最优。

## 输入协议

UTF-8 JSON 对象（字段顺序任意）：

| 字段 | 含义 |
| --- | --- |
| `cassette_count` | 钞箱数，整数 2–6 |
| `denominations` | 候选面额，非空正整数数组（重复/乱序会被去重并升序规范化） |
| `cassette_capacity` | 单箱容量，正整数 |
| `total_note_limit` | 整机初始总张数上限，正整数且 ≤ 钞箱数×单箱容量 |
| `initial_cash_limit` | 初装资金上限，非负整数 |
| `withdrawals` | 提款金额序列，非负整数 |
| `penalties` | 与提款等长的罚值序列，非负整数 |
| `transport_cost_per_note` | 每张初装钞票的运钞成本，非负，默认 0 |
| `load_cost_per_cassette` | 每个实际使用钞箱的补货成本，非负，默认 0 |
| `search_budget` | 可选正整数；省略或 null 表示不限 |

非法输入按类别抛不同异常（`errors.py`，CLI 以退出码 2 输出到 stderr）：
`SchemaError`（结构/类型/缺字段/非法 JSON）、`ValueError_`（负数、零容量）、
`ConstraintError`（字段互相矛盾）、`DenominationError`（面额列表不可用）、
`CassetteCountError`（钞箱数越界）、`BudgetError`（预算非法）。

## 输出协议

规范化 JSON（键排序、2 空格缩进、末尾换行），主要字段：

- `status`：`optimal` / `incomplete`；`optimal`：布尔证明标志；
- `objectives`：四层目标实际值；`objectives_basis`：每层的公式、逐项明细与值，
  拿原始输入可逐项复算（失败下标、每箱面额×张数、成本各项、每笔吐钞张数）；
- `plan.denomination_vector`、`plan.initial_counts_vector`；
- `plan.withdrawals[]`：每笔 `index/amount/satisfied/dispensed/stock_before/stock_after`，
  可完整回放，逐笔重算库存；
- `bounds.upper_bound`、`bounds.lower_bound`、`explored_states`、`search_budget`、
  规范化后的 `input`。

## 输入输出示例

见 `examples/example_input.json` 与 `examples/example_output.json`（由 CLI 生成）。

```json
{
  "cassette_count": 3,
  "denominations": [50, 20, 10],
  "cassette_capacity": 20,
  "total_note_limit": 40,
  "initial_cash_limit": 2000,
  "withdrawals": [60, 80, 40, 70],
  "penalties": [100, 100, 100, 100],
  "transport_cost_per_note": 1,
  "load_cost_per_cassette": 5
}
```

该例最优：面额向量 `[0, 20, 50]`、初装 `[0, 10, 1]`，
目标 `(penalty=0, cost=21, cash=250, notes=11)`。

## 复现命令

```bash
# 直接运行（Python 3.12；也可 python -m pip install -e . 后用 atm-optimizer）
python -m atm_optimizer.cli examples/example_input.json

# 从标准输入读取
type examples\example_input.json | python -m atm_optimizer.cli   # Windows
cat examples/example_input.json | python -m atm_optimizer.cli    # POSIX

# 运行全部自动化测试
python -m unittest discover -s tests -v
```

## 模块结构

- `atm_optimizer/errors.py`：分类异常体系；
- `atm_optimizer/model.py`：不可变数据类型；
- `atm_optimizer/validate.py`：解析、分类校验、规范化；
- `atm_optimizer/dispense.py`：有限库存下的精确凑额完整枚举；
- `atm_optimizer/loading.py`：装载配置规范序流式枚举 + 分支定界；
- `atm_optimizer/sequence.py`：固定装载的集合 DP 与支配剪枝；
- `atm_optimizer/planner.py`：联合优化主循环、松弛下界、预算处理；
- `atm_optimizer/protocol.py`：规范化 JSON 与目标计算依据；
- `atm_optimizer/cli.py`：命令行入口。

## 测试覆盖

- 有限库存找零（与 itertools 全枚举逐向量一致）、重复面额钞箱；
- 提款序列依赖（贪心会导致后续失败的场景）、并列最优的向量裁决；
- 面额输入顺序变化与重复运行的逐字节确定性；
- 状态支配剪枝、装载级分支定界分别与无剪枝全枚举一致；
- 搜索预算耗尽（上界/可证下界/状态数/未证明标记）；
- 小规模全枚举 oracle 核对整个嵌套优化（固定用例 + 60 个随机实例）；
- CLI 成功输出、非法 JSON/校验错误退出码与分类、预算耗尽仍退出 0。
