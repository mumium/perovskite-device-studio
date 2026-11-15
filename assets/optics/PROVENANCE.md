# 内置光学数据来源

## AM1.5G

`AM1.5G_ASTMG173.csv` 为官方 ASTM G173 参考太阳光谱原始四列表格，未修改数值。下载于 2026-10-14。

- 官方说明：https://www.nlr.gov/grid/solar-resource/spectra-am1.5
- 原始压缩包：https://www.nlr.gov/media/docs/libraries/grid/zip/astmg173.zip?sfvrsn=1ef05e45_5
- 使用 Global Tilt 列，波长单位 nm，辐照度单位 W/m²/nm；2002 个样本，280–4000 nm。
- 原始梯形积分 1000.3706555734423 W/m²。运行时按完整积分缩放到用户 Pin，不将局部波段重新归一化。

## 示例 n,k

以下 `nk_*.txt` 均原样取自 [SIMsalabim v5.36 Data](https://github.com/kostergroup/SIMsalabim/tree/v5.36/Data)，下载于 2026-10-14。上游文件使用波长 m、无量纲 n/k；程序显示和用户 CSV 使用 nm。

这些是软件演示数据，不代表当前样品，也不由输入的 Eg、χ、掺杂或材料名称推导。原始文件内容保持不变；上游许可证见 [COPYING](../../vendor/simsalabim/COPYING.txt)。MAPI 数据不能自动代表所有钙钛矿配方。

| 文件 | 覆盖范围 / nm | 上游 |
| --- | --- | --- |
| `nk_Ag.txt` | 300–800 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_Ag.txt) |
| `nk_Air.txt` | 300–800 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_Air.txt) |
| `nk_Au.txt` | 300–900 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_Au.txt) |
| `nk_C60_1.txt` | 300–1100 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_C60_1.txt) |
| `nk_ITO.txt` | 300–800 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_ITO.txt) |
| `nk_MAPI.txt` | 300–900 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_MAPI.txt) |
| `nk_PTAA.txt` | 300–1100 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_PTAA.txt) |
| `nk_SiO2.txt` | 300–800 | [原文件](https://raw.githubusercontent.com/kostergroup/SIMsalabim/v5.36/Data/nk_SiO2.txt) |

以上为保留的旧示例，其共同范围为 300–800 nm。1.4.3 新建配置改用下面列出的宽波段条目，默认计算 300–1100 nm；显式保存旧条目/波段的项目保持原值。扩大波段仍须所有相关 n,k 覆盖，程序禁止外推。

`example_nk.csv`、`example_spectrum.csv` 是本项目创建的文件格式示例，数值为人为设定，不是实测材料/太阳光谱。

## 原始文件 SHA256

- `AM1.5G_ASTMG173.csv`：`b48a6635ce398f7e0fa392150d68b5793ed7f2a65d9e2406bec7e6be9fb20954`
- `nk_Ag.txt`：`c4af6e7c9d2988c25cf32ce2cc7f1b2c1e4dd6347ccb0fb464a366a15acc1fbc`
- `nk_Air.txt`：`793502e5d07585ea10e5a9ff41989c840bc7ede814b4b51f04dadf83f3b7c913`
- `nk_Au.txt`：`42e154e6eb4a2a8a4f81abf3fa6956f0f98d5576cea680d70b82eb0a000c3f49`
- `nk_C60_1.txt`：`8bf21768c85598bf08c629503cd76c605882c25967b5fae9a451142bbfec4414`
- `nk_ITO.txt`：`55da4383b523c5688a6af0f2b06ec45a9f00443a4edc94c3a3af37171cbf9d1f`
- `nk_MAPI.txt`：`ee62ba48964354946e85bf177ecad7db82a0c517c6e285e8d026840abb0b3fbf`
- `nk_PTAA.txt`：`d3207d6c80f493492a3622f3fbae23b634f7d07df8d586c1b607e7887c72d1b7`
- `nk_SiO2.txt`：`faf0ae0fd474b2c730cc931bcb8d9244599dc2b5b468203e6d52ba44b7978c40`

## 1.4.3：新建默认 300–1100 nm 的独立条目

没有拼接或延长旧示例曲线。旧文件与旧内置键名保持原样，新建默认使用独立的文献数据条目；相同材料名不代表相同样品，改变来源会改变计算结果。

| 新条目 | 来源与范围 | 说明 |
|---|---|---|
| ITO · Minenkov | Minenkov et al. 2024，191.46–1688.69 nm | 原作者提供给数据库的 110 nm ITO/玻璃样品拟合 n,k；这里只作为默认示例，软件设置的 200 nm 是模拟膜厚，并非新测量 |
| MAPI · Phillips | Phillips et al. 2015，约300–1501.3 nm | 硅片上两步气相法 MAPI 薄膜；不能替代宽带隙或锡铅钙钛矿的实际数据 |
| Ag · Johnson | Johnson & Christy 1972，187.9–1937 nm | 独立完整文献表，不向原300–800nm旧表补尾 |
| Au · Johnson | Johnson & Christy 1972，187.9–1937 nm | 同上，供可选背电极 |
| Air · 1100 | 300–1100 nm，n=1，k=0 | 理想空气近似，非测量表 |
| SiO2 · Malitson | Malitson 1965 Sellmeier，采样300–1100 nm | 熔融石英色散，k=0为透明近似；非实测沉积膜 |

PTAA 与 C60 继续使用原本已到1100nm的示例表。新默认入射基底/前透明电极为 ITO · Minenkov，背电极为 Ag · Johnson，吸收层示例为 MAPI · Phillips。MAPI 吸收边联动参考 Eg=1.55 eV 仍是软件演示约定，不是对文献样品带隙的测定。

原始数据库快照固定在 `polyanskiy/refractiveindex.info-database` 提交 `e6d15e364f70de1cad8a96a20f75689f2fba8b21`，数据许可证 CC0 1.0。原始 YAML（保留作者、DOI、样品说明）及哈希清单位于 `sources_1100/`。这些是文献样品的代理数据，未对当前用户材料标定。

- ITO：A. Minenkov et al., *ACS Applied Materials & Interfaces* 16, 9517–9531 (2024)，https://doi.org/10.1021/acsami.3c17923 。数据库路径 `database/data/other/mixed crystals/In2O3-SnO2/nk/Minenkov-glass.yml`。
- MAPI：L. J. Phillips et al., *Data in Brief* 5, 926–928 (2015)，https://doi.org/10.1016/j.dib.2015.10.026 。论文报告300–1500nm。数据库从能量转换出的首点为300.009583nm；导入时仅将波长坐标量化到0.1nm，移动不足0.05nm，所有n/k值原样保留，以统一300nm端点。没有外推吸收谱。路径 `database/data/other/perovskite/CH3NH3PbI3/nk/Phillips.yml`。
- Ag/Au：P. B. Johnson & R. W. Christy, *Physical Review B* 6, 4370–4379 (1972)，https://doi.org/10.1103/PhysRevB.6.4370 。路径 `database/data/main/Ag/nk/Johnson.yml` 和 `database/data/main/Au/nk/Johnson.yml`。
- SiO2：I. H. Malitson, *JOSA* 55, 1205–1208 (1965)，https://doi.org/10.1364/JOSA.55.001205 。路径 `database/data/main/SiO2/nk/Malitson.yml`。

运行 `python scripts/build_optics_1100.py` 可从已保存源文件重建新数据表与哈希清单，不访问网络，也不修改旧表。文件格式仍为波长m、无量纲n/k；程序内部以1nm步长在线性插值范围内计算。
