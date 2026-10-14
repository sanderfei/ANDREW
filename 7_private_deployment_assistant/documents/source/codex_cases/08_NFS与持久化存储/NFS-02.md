# NFS-02：PV PVC与NFS目录及卸载后旧数据复用

项目：g_kube_installer / g_web_installer。记录状态：源码结论。来源会话起始日期：2026-08-11（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## NFS-02 问题与表现

helm uninstall后密码/初始化不变；删namespace后旧文件仍有archived目录。

## NFS-02 最终根因或已确认边界

StatefulSet→PVC→StorageClass/provisioner→PV/NFS子目录是多层生命周期。历史nfs-default为Delete+archiveOnDelete，helm卸载一般保留StatefulSetPVC，namespace删除则删除PVC。

## NFS-02 处理方案

先查实际PVCUID/PV/StorageClass及NFS子目录。同名release复用旧PVC会沿用旧数据库和密码；archived-*只是回收行为，不是已验证备份。RWO限制一个node写，非单Pod或数据库HA；勿用kubectl delete all代替Helm管理。

### NFS-02 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
kubectl get storageclass
kubectl get pvc -A
kubectl get pv
helm status mariadb -n mariadb
```

## NFS-02 验证证据与限制

源码与Chart行为核对；没有授权执行此文档中的数据删除。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## NFS-02 来源定位

- Codex 会话 `019fefb1-1e45-70b3-a81f-bce94029fe79`；始于 2026-08-11。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
