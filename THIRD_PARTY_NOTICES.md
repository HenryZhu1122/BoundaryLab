# 第三方工具与研究来源

芯界的实验编排、验收、界面与证据导出为本项目实现，开发过程中使用了 AI 辅助。没有复制论文仓库中的 Agent 代码。引用研究思路不代表已经复现论文成绩。

## ngspice 47

使用官网提供的未修改 Windows x64 发行版。原始下载地址：

https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/47/ngspice-47_64.7z

官方主页：https://ngspice.sourceforge.io/  
版本源码目录：https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/

发行版含多个来源的组件，具体许可全文及例外列表保留在 `vendor/Spice64/docs/COPYING`，作者列表在 `vendor/Spice64/docs/AUTHORS`。原始二进制及伴随文件未改动。文档与模型示例遵从各自声明；不把全部第三方文件重新许可为 MIT。

## Python 运行依赖

FastAPI、Starlette、Pydantic、Uvicorn、NumPy、HTTPX、python-dotenv 通过 pip 安装，版本在 requirements.txt 中固定，遵守各自发行版内的许可声明。评测和图表工具列在 requirements-dev.txt；浏览器测试使用 Playwright。用户无需安装 Node.js 即可运行主作品。

## 研究启发

1. Large Language Models as Falsifiers for Cyber-Physical Systems. arXiv:2609.20752v1. https://arxiv.org/abs/2609.20752
2. LLM-IDEA: Identifiability-Driven Experimental Agent for Autonomous Discovery of Mechanistic World Models. arXiv:2610.11253v1. https://arxiv.org/abs/2610.11253
3. AnalogAgent: Self-Improving Analog Circuit Design Automation with LLM Agents. arXiv:2603.23910. https://arxiv.org/abs/2603.23910
4. Explore or Confirm? LLM Agents Misallocate Measurements Under Noise. arXiv:2610.25111. https://arxiv.org/abs/2610.25111

芯界借鉴工具反馈、证伪与实验选择的研究方向，贡献定位于面向电路科研与学习的可运行系统及其可复查记录，不宣称提出上述论文的方法或取得其结果。
