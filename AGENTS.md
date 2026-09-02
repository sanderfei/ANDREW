# Repository instructions

- 当仓库在新电脑首次运行或环境未就绪时，先阅读 `docs/setup-new-machine.md`；环境验证通过后再按 `docs/learning-handoff.md` 继续。
- 处理 `3_rag_from_scratch` 学习任务前，先阅读 `docs/learning-handoff.md`，从其中的“下一步”继续，不要重复已经完成的内容。
- 当用户提出“下班交接”“同步学习进度”或明确要求更新交接文档时，更新 `docs/learning-handoff.md` 中的当前进度、已验证命令和下一步。
- 不要把 API Key、Token、`.env` 内容或原始 Codex 会话记录写入仓库文档。
- 我问你的python语法都写入当前项目的python基础语法文档中，不是所有的python相关的问题都要加进去，只要对应的python基础语法加入文档即可
- 新的langchain学习相关的语法也加入langchain基础语法
- 新的langgraph学习相关的语法也加入langgraph基础语法（如果没有就创建一个langchain同级目录文件）
- 当我说“提交代码”时，不要额外修改、测试、构建、格式化或执行发布检查；只暂存我点名范围内的对应代码，直接 commit 并 push 到 GitHub main 分支，同时保留无关工作区改动
- 每个可运行文件 main 方法上面添加注释，当前文件的启动命令示例以及参数枚举
