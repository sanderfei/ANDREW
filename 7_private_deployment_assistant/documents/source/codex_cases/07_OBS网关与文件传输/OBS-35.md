# OBS-35 私有化 OBS 最后一片上传成功后重复关闭合并文件返回 500

记录日期为 2026-11-23。环境为私有化部署，接口是 `POST /api/v1/privatization/obs/file/upload`，服务端实现按 `private-service c41b48f9` 核对。现场部署包版本待确认。

## 现象

第 5/5 片触发合并，网关 PUT 记录的对象大小为 99,597,998 字节，返回 HTTP 201。随后私有化接口报“文件已上传，但关闭合并文件失败”，整次请求约 4.05 秒，最终 HTTP 500。前一轮两次 XHR 在 10.02 秒显示 canceled，仍单独追踪于 [OBS-34](OBS-34.md)。

## 根因与影响

`internal/app/service/privatization/service.go:5387` 将合并后的 `*os.File` 传给上传函数，`internal/app/pkg/util/obs.go:172`、`:191` 用它创建并发送 HTTP 请求。标准库对实现了 `io.ReadCloser` 的传入对象直接用作请求体，HTTP 传输层会关闭请求体。随后 `service.go:5392` 再次调用 `merged.Close()`，这条失败分支返回了日志中的错误。

网关操作的成功条件包括状态码 201 和响应中的 key、size 匹配（`internal/app/pkg/util/obs.go:333`）。按这版源码，走到报错位置时，`obsUploadFile` 也已成功结束数据库事务。错误发生在清理本地临时文件期间。提前返回还跳过了 `service.go:5395` 的整批分片目录清理，可能留下已接收的分片和总数标记。现场对象与数据库现状需要按同一路径核对。

## 处理与验证

1. 查询私有化资源列表和 OBS 对象，核对同一文件的路径及精确字节数 99,597,998，避免直接重传触发覆盖。
2. 修复方向是明确文件句柄归属。例如，分片层向上传函数提供一个仅用于读取的请求体包装，由分片层统一关闭底层临时文件，并处理分片目录清理。保留真实的网关传输和数据库写入失败信息。
3. 用可控 HTTP 服务接收多片合并后的 PUT，检查请求体内容和大小；随后检查最终上传接口应返回 `merged=true`、`success=true`，列表和 OBS 对象大小一致，临时分片目录已清理。

## 验证结果

本机用实际 `OBSGateway.Put`、标准 HTTP Transport、本地 `httptest.Server` 和真实临时文件测试。直接传 `*os.File` 时，PUT 成功后调用方再次 Close 命中 `os.ErrClosed`；传 `io.NewSectionReader` 时，PUT 成功后调用方 Close 也成功。两组断言均通过，确认了文件句柄归属对该错误的影响。现场修复、部署以及修复后的完整上传仍待验证。
