# 两子电池串联参考重建

打开[报告](串联参考重建报告.html)。软件1.4.1新增同电流、电压相加的独立参考模式，复用同一完整堆栈G(x)。两种能级/光学案例的零额外连接电阻参考Voc约2.095/2.074V、效率21.12%/29.66%。

**它采用虚拟选择性内接触，不是已验证实际20n/20p连接的自洽隧穿仿真，不预测材料接触是否有效。** 未增加独立物理互联层，也未手动抬高Voc。

parameters需要1.4.1打开。完整数据包在[v1.4.1发布](https://github.com/mumium/perovskite-device-studio/releases/tag/v1.4.1)中的series-reference-2026-11-15.zip。操作和限制见[说明](../../../docs/tandem-reference.md)。
