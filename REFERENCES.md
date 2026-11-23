# 参考文献与设计依据

[English](REFERENCES.en.md) | 中文

本工具中每个判据都能追溯到下面某一条。编号在代码与报告中以 `[S#]` 形式引用。

| 编号 | 文献 | 用它支撑什么 | 链接 | 访问日期 |
|---|---|---|---|---|
| **S1** | Socrates, G. *Infrared and Raman Characteristic Group Frequencies: Tables and Charts*, 3rd ed., Wiley, 2004. ISBN 978-0-470-09307-8 | 官能团频率区间（C=O 细分、羧酸盐 1550-1610、芳环面外弯曲等） | [Google Books](https://books.google.com/books?id=LDoAAjMnwEIC) | 2026-11-24 |
| **S2** | Larkin, P. *Infrared and Raman Spectroscopy: Principles and Spectral Interpretation*, Elsevier, 2011. ISBN 978-0-12-386984-5 | 频率区间与谱带形状的对应关系（宽包 vs 尖峰） | [Google Books](https://books.google.com/books?id=KPyV1DRMRbwC) | 2026-11-24 |
| **S3** | Coates, J. "Interpretation of Infrared Spectra, A Practical Approach", in *Encyclopedia of Analytical Chemistry*, Wiley | 无机填料与骨架振动区的干扰（碳酸钙 873/712、硅酸盐） | [ScienceDirect topic](https://www.sciencedirect.com/topics/materials-science/group-frequency) | 2026-11-24 |
| **S4** | 中国药典 2025 年版四部 通则 0402《红外光谱法》 | 峰位偏差 ±5 cm⁻¹ 或 0.5%；ATR 与透射谱不可直接比对；相似度阈值须预设并验证；晶型需另法佐证 | [2025.chp.org.cn](https://2025.chp.org.cn/#/item?bookId=4&entryId=5578) | 2026-11-24 |
| **S5** | GB/T 6040-2019《红外光谱分析方法通则》 | 信噪比 < 3 的峰不得作为定性依据 | 国家标准全文公开系统 | 2026-11-24 |
| **S6** | Levine, S. P.; Lowry, S. R.; Tomellini, S. A.; et al. *Anal. Chem.* **1987**, 59(17), 2197-2203 | 规则/专家系统自动归属的**假阳性率 19.4%、假阴性率 1.2%**（62 化合物 + 67 个四组分混合物）；失败原因含峰位漂移、结构相似、肩峰未分辨 | [CDC Stacks](https://stacks.cdc.gov/view/cdc/185319) | 2026-11-24 |
| **S7** | Affolter 等，转引自 *Chem. Sci.* 2023, "Automatic materials characterization from infrared spectra using convolutional neural networks" | **频率区间表不能直接用于自动解谱**：直接套用文献区间会导致大量"应有峰却无峰"的情形，因此缺峰不能否定基团 | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2041652023061370) | 2026-11-24 |
| **S8** | Coblentz Society, *Field Guide*, Chapter 9: ATR Spectroscopy — Physics, Approximations, and Best Practices | ATR 谱带相对振荡位置**红移**、峰形不对称、可能出现本不存在的肩峰/分裂；与透射谱库比对会产生假阳性/假阴性 | [coblentz.org](https://www.coblentz.org/field-guide/chapter9/) | 2026-11-24 |
| **S9** | Mayerhöfer, T. G.; Costa, W. D. P.; Popp, J. *Appl. Spectrosc.* **2024**, 78(3), 321-328（及 2025 简化 ATR 校正） | ATR 校正可修正峰位，但峰强未必可靠；不校正则峰位系统性偏移 | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1386142525007310) | 2026-11-24 |
| **S10** | Thermo Fisher, Application Note AN50733: *Curve Fitting in Raman and IR Spectroscopy* | 拟合组分过多必然改善残差但组分可能无物理意义；低残差不能证明组分真实；信噪比不足时拟合与二阶导数都不可靠 | [PDF](https://documents.thermofisher.com/TFS-Assets/CAD/Application-Notes/AN50733_E.pdf) | 2026-11-24 |
| **S11** | *Appl. Sci.* **2026**, 16(21), 10552（胶原纤维化 FTIR 综述） | 分峰结果是**非唯一解**：峰宽相近的组分可互换强度而拟合几乎不变；面积百分比依赖组分数、线型、约束与窗口，跨实验室不可直接比较 | [MDPI](https://www.mdpi.com/2076-3417/16/21/10552) | 2026-11-24 |
| **S12** | "Automatic identification of compounds in molecular mixtures from liquid-phase infrared spectra", *PMC* 2025 | 液相混合物自动识别准确率上限约 90%，受限于近 identical 的谱图；混合物场景无法做到 100% | [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13224293/) | 2026-11-24 |
| **S13** | ASTM E1252-98(2021), *Standard Practice for General Techniques for Obtaining Infrared Spectra for Qualitative Analysis* | 定性红外的采谱与评估规范；明确"比较须使用相同技术与相同条件"，且"已发表参考谱并非全部经过完整验证" | [astm.org](https://www.astm.org/e1252-98r21.html) | 2026-11-24 |
| **S14** | 欧洲药典 通则 2.2.24 *Infrared Spectrophotometry* | 制样规范（压片 1-2 mg 样品 / 300-400 mg KBr；2000 cm⁻¹ 处透光率低于 60% 判为废片）；鉴别须同法同条件测对照品 | [Ph. Eur. 2.2.24（镜像）](https://www.drugfuture.com/Pharmacopoeia/BP2010/data/1001.html) | 2026-11-24 |
| **S15** | USP <854> *Mid-Infrared Spectroscopy* | 仪器确证与操作要求（波数准确度、分辨率、系统适用性）；原料鉴别试验引用该章 | 引用自 USP–NF，全文需订阅 | 2026-11-24 |
| **S16** | NIST Chemistry WebBook, SRD 69 | 公开参考谱入口（气相/凝相红外） | [webbook.nist.gov](https://webbook.nist.gov/chemistry/) | 2026-11-24 |
| **S17** | SDBS, AIST（日本产业技术综合研究所） | 有机物谱库（IR / Raman / NMR / MS），免费 | [sdbs.db.aist.go.jp](https://sdbs.db.aist.go.jp/) | 2026-11-24 |
| **S18** | Coblentz Society Spectral Database | 专业红外谱库（订阅），谱图经评审 | [coblentz.org](https://www.coblentz.org/) | 2026-11-24 |
| **S19** | *Indonesian J. Sci. Technol.* **2022**, "Interpretation of FTIR Spectra: A Practical Approach in the Polymer/Plastic Thermal Decomposition" | 面向实操的判读流程示例（先官能团区、后指纹区） | [DOI](https://doi.org/10.17509/ijost.v8i1.53297) | 2026-11-24 |
| **S20** | ASTM E2310-04(2014), *Standard Guide for Use of Spectral Searching by Curve Matching Algorithms with Data with Mid-infrared Spectroscopy* | 中红外谱库检索的唯一权威指南：明确 HQI 无统一定义、由各软件自行规定；列出欧氏距离、相关系数、一阶导数欧氏距离等算法；指出强带主导归一化会使弱指纹带失效，并强调数据点须先对齐 | [astm.org](https://www.astm.org/e2310-04r14.html) | 2026-11-24 |

## 这些文献如何影响工具设计

| 设计决定 | 依据 |
|---|---|
| 结论措辞用"支持存在 / 提示可能含 / 不构成结构确证"，不用"确证" | S6、S7、S12 |
| 每份报告固定输出 6 条「可信度声明」，含 19% 假阳性率提示 | S6 |
| 归属必须"两条以上独立谱带"才升为「支持」，单带只给「提示」 | S6、S7（单带易受相似结构干扰） |
| 明确写"某区间没有峰不能否定该基团" | S7 |
| 峰表增加「可信度」列，并列出竞争归属 | S6（结构相似是主要失败原因） |
| 水峰与 O-H/N-H 重叠时强制降级并提示干燥复测 | S1、S2 |
| ATR 谱不与透射谱/谱库直接比对，写入声明 | S8、S9、S4 |
| 分峰拟合结果标注"非唯一"，不用作绝对百分比 | S10、S11 |
| 拒绝在饱和或信噪比 < 3 时给归属结论 | S5 |
| 相似度判定阈值需预设并可调，报告注明来源 | S4 |
| 报告固定附「方法学参考」清单（S1/S3/S13/S14/S19） | S13、S14 |
| 报告固定附「交叉验证建议」，按识别到的基团给出正交手段 | S4、S14、S15 |
| 文献线索只作关键词线索，明确标注"不是同一化合物" | S13、S16-S18 |
| 比对加入一阶导相关，并在两条相关判据矛盾时降级为「需复核」 | S20 |
| 峰位由三点抛物线插值定位（不满足条件时退回栅格值） | S4（±5 cm⁻¹ 判据需要更细的位置分辨） |
| 肩峰需「不对称 + 二阶导极大」双条件，不用单一 FWHM 阈值 | S1、S3 |
| 不实现名为 HQI 的单一得分：ASTM 明确 HQI 无统一定义 | S20 |

## 关于「从论文里找相同谱图」

**做不到，也不假装做到。** 公开检索接口（OpenAlex、Europe PMC）只能按关键词匹配标题与摘要，**没有按谱图相似度检索的能力**。因此工具给出的是"同类谱型的判读讨论"，用来对照别人的归属惯例，不能用来证明你的样品是同一个化合物。

真正的同谱比对只有三条路：

1. **谱库检索**：NIST WebBook / SDBS（免费）、Coblentz、KnowItAll-Sadtler（订阅）。注意库检索的固有问题——未收录化合物必然找不到，且"最高分"未必正确（S6、S12）。
2. **对照品比对**：同条件、同制样方式测定对照品，这是药典路径（S4、S14）。
3. **正交手段确证**：NMR、MS、XRD、元素分析（S4、S12）。

## 尚不能解决的限制（诚实列出）

1. **没有谱库**：不做库检索。文献明确指出，未收录的化合物无法被库检索识别，且"最高分"未必是正确答案（见 S6、S12 的讨论）。所以我们只做官能团层面的假设，不做化合物身份判定。
2. **混合物**：多组分重叠时，单组分归属的可靠性显著下降（S12 的上限约 90%，且那是算法而非规则法）。
3. **结晶度/晶型**：红外只能提示"有序度变化"，不能判定晶态或晶型，必须用 XRD。
4. **定量**：不做含量测定。药典的定量路径是外标法/标准曲线/多变量校正，需要系列标准样。
5. **无按谱检索能力**：不接入谱库、不做相似度匹配，只能给关键词线索（见上一节）
6. **ATR 未做数值校正**：当前只做提示，不实现 Kramers-Kronig 或色散校正（需要折射率等额外参数，S9）。
