"""预留 Web 集群列表、config.yaml 摘要和任务历史的读取入口。"""


class WebInstallerAdapter:
    def list_clusters(self) -> dict:
        # 后续对接认证后的 GET /api/v1/clusters，当前不发起网络请求。
        return {
            "status": "not_connected",
            "items": [],
            "message": "Web 服务器连接尚未接入。",
        }

    def get_cluster_context(self, cluster_name: str) -> dict:
        # 后续读取集群详情，按字段白名单构造摘要，排除密码、私钥等内容。
        # 配置摘要和实际运行状态应分别标明来源与采集时间。
        raise NotImplementedError("集群配置读取尚未接入。")
