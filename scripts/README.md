# 维护脚本

`build_windows.py` 根据 `APP_VERSION` 将 Windows 单文件版输出到 `dist/<版本号>/`，追加 `--folder` 构建文件夹版；可用 `--no-clean` 复用构建缓存。根目录 `build_exe.bat` 调用此脚本。

`build_icons.py` 将原有 `assets/logo.png` 编码为包含 14 档尺寸的 `assets/logo.ico` 与 256 px 的 `assets/logo-window.png`，不修改原稿。需要 Pillow，运行 `python scripts/build_icons.py`；日常启动程序不需要 Pillow。

`prepare_simss_source.py` 从上游 SIMsalabim v5.36 源码生成本项目分发的求解器源码，包含网格预算、2000 点上限和稳态界面 SRH 雅可比修正。

在项目根目录运行：

```powershell
python scripts/prepare_simss_source.py C:/path/to/SIMsalabim-5.36
```

输出在 `vendor/simsalabim/source/`。日常使用桌面工具不需要运行此脚本；不会重新编译或替换现有 SimSS 可执行文件。

`check_interface_jacobian.py` 将分发的 Pascal 复合例程与中心有限差分比较，含两处界面和不对称电子/空穴捕获系数。Windows 使用便携 Free Pascal 3.2.2 目录：

```powershell
python scripts/check_interface_jacobian.py --fpc-root build/fpc-portable/app
```

测试仅在临时副本中导出内部例程，不修改正式源码或求解器。测试程序源文件为 `tests/interface_jacobian.pas`。

`build_optics_1100.py` 从 `assets/optics/sources_1100/` 的固定文献源表重建新建配置所用的宽波段数据和哈希清单，不联网、不修改旧内置表。数据范围、样品限制和波长坐标量化说明见 [光学来源](../assets/optics/PROVENANCE.md)。
