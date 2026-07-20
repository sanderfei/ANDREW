"""Part 2 补充：用五组 token-aware 参数比较切块与检索结果。"""

from __future__ import annotations

try:
    from ._common import (
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_vector_store,
        count_tokens,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
    )
except ImportError:
    from _common import (
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_vector_store,
        count_tokens,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
    )


CHUNK_QUESTION = "chunk overlap 为什么能减少切块边界的信息丢失？"
# 两组同尺寸对照用来隔离 overlap 的影响，最后一组观察大 chunk 的噪声。
# 综合完整性与成本：80/10 最均衡。
# 优先保留完整因果链：140/30 更好，但上下文更贵。
# 260/60 的 Top-1 分数最高，但 Top-2 上下文最大，不能因此判定它最好。
CHUNK_CONFIGS = (
    {"chunk_size": 80, "chunk_overlap": 0},
    {"chunk_size": 80, "chunk_overlap": 10},
    {"chunk_size": 140, "chunk_overlap": 0},
    {"chunk_size": 140, "chunk_overlap": 30},
    {"chunk_size": 260, "chunk_overlap": 60},
)

LOCAL_LONG_DOCUMENT = Document(
    page_content="""
实验说明：这份材料用于比较切块参数如何改变检索结果。实验只调整chunk_size与chunk_overlap，文档内容、问题、embedding模型、向量库和top-k保持不变。这样才能把结果差异归因到切块方式，避免把模型变化或问题改写误认为参数效果。材料同时放入明确答案、相关背景、近义术语和无关细节，用来检验检索是否既能召回答案，又能控制噪声。

索引背景：RAG的indexing通常在用户提问前完成。加载器先把原始资料转换成Document，切块器再把长文本拆成多个可检索片段。embedding模型为每个片段生成向量，向量库同时保存向量、page_content和metadata。查询到来后，系统只为问题生成查询向量，再计算它与各个片段向量的相似度。生成模型看不到整篇原文，也看不到向量数字，只能看到进入top-k的文本片段。因此，切块是否保留完整语义会直接限制后续回答质量。

块大小取舍：chunk_size太小时，索引里会出现很多短片段。短片段通常主题集中，单次召回消耗的token较少，但一个定义、条件和结论可能被拆到不同片段。chunk_size太大时，片段更容易包含完整上下文，却也可能把多个主题绑在一起。查询只需要其中一句答案，召回结果却顺带携带实现背景、例外情况和其他术语，不仅稀释向量语义，还会占用prompt预算。合适大小不是固定常数，应结合文档结构、问题粒度和模型上下文长度评估。

分隔规则：递归字符分隔器会优先尝试段落、换行和空格等自然边界；只有较大的文本单元仍然超过预算时，才继续使用更细的分隔方式。from_tiktoken_encoder把chunk_size和chunk_overlap解释成token预算，而metadata中的start_index仍是原文字符位置。由于中英文、数字和标点的token化方式不同，八十个token并不等于八十个汉字。重叠值只是可争取的预算，也不保证每对相邻片段都机械地重复完全相同的token数。

关键机制：先明确答案，chunk_overlap不是在检索完成后修复被截断的句子，而是在索引切块时把边界附近的一小段原文重复放进相邻片段。假设一个关键解释同时包含问题对象、触发条件和因果结论，而切点恰好落在条件与结论之间；完全不重叠时，前一个片段可能只保留问题对象和触发条件，后一个片段可能只保留因果结论。两边单独看都缺少必要线索，查询向量与它们的相似度可能下降，top-k也可能只召回其中一半。加入适量重叠后，相邻片段共享切点附近的桥接文本，至少一个片段更有机会同时保留主语、条件和结论。因此，chunk_overlap能减少切块边界造成的信息丢失，并提高完整证据进入top-k的概率。它的作用不是凭空产生新知识，而是让原文中已有的局部上下文在边界两侧重复出现。

边界例子：原文可能写着“订单只有在支付成功并通过库存校验后，才允许进入发货队列”。如果零重叠切点落在库存校验附近，前块包含支付与库存条件，后块只包含允许发货的结论。用户询问发货条件时，任何单块都可能不完整。若后一个片段向前重复少量文本，它就可能获得“通过库存校验后，才允许进入发货队列”这段连续证据，条件与结论重新出现在同一个检索单元中。这里真正有价值的是桥接语义，而不是简单增加字符数量。对于代码、表格、标题层级或跨段引用，合理的分隔符往往与重叠同样重要。

重叠成本：重叠并非越大越好。chunk_overlap增大会让同一内容被多次embedding，并增加向量条目中的重复信息、内存和持久化空间。检索时，top-k可能被两个高度相似的相邻片段占满，导致其他互补证据没有位置；送给生成模型的上下文也可能反复出现同一句话，增加token成本并诱发重复回答。当重叠已经接近块大小时，有效新增内容很少，索引效率会明显下降。因此应寻找足以覆盖典型边界语义、又不会制造大量重复的范围。

评估方法：不能只看chunk_count，也不能只盯着最高score。应该检查正确证据是否稳定进入top-k、命中片段是否同时保留主语与结论、是否夹带大量无关主题、相邻结果是否高度重复，以及最终注入prompt的token总量。还要固定embedding模型与检索参数，分别用相同chunk_size对比不同chunk_overlap，才能判断改善是否真的来自重叠。向量检索依赖语义接近，不是关键词精确匹配；讨论上下文窗口、token预算、文本重复或文档边界的片段可能得到不低分数，却没有回答为什么重叠能够保护边界。本实验使用三百八十四维本地多语言向量，维度数字本身与边界保护机制无关；若这类背景进入top-k，就应按噪声分析。
""".strip(),
    metadata={"source": "chunking-lab.md", "topic": "chunking"},
)


def _top_matches(vector_store, question: str, k: int = 2) -> list[dict[str, object]]:
    return [
        {
            "score": round(float(score), 6),
            "start_index": document.metadata.get("start_index"),
            "token_count": count_tokens(document.page_content),
            "content": " ".join(document.page_content.split())[:280],
        }
        for document, score in vector_store.similarity_search_with_score(question, k=k)
    ]


def main() -> None:
    options = parse_runtime_options("RAG Part 2 补充：切块参数对比")
    documents = (
        load_source_documents(True)
        if options.use_web_source
        else [LOCAL_LONG_DOCUMENT]
    )
    question = DEFAULT_QUESTION if options.use_web_source else CHUNK_QUESTION
    embeddings = build_embeddings(mode=options.embedding_mode)

    experiments: list[dict[str, object]] = []
    for config in CHUNK_CONFIGS:
        # 函数定义中的单个 * 让后续参数只能按名称传递；调用处的 **config
        # 则把字典展开成 chunk_size=...、chunk_overlap=... 两个关键字参数。
        chunks = split_documents_token_aware(documents, **config)
        token_counts = [count_tokens(chunk.page_content) for chunk in chunks]
        vector_store = build_vector_store(chunks, embeddings=embeddings)
        experiments.append(
            {
                **config,
                "chunk_count": len(chunks),
                "chunk_token_min": min(token_counts),
                "chunk_token_max": max(token_counts),
                "chunk_token_average": round(sum(token_counts) / len(token_counts), 2),
                "top_matches": _top_matches(vector_store, question),
            }
        )

    print_json(
        "Part 2 - Chunking Parameter Comparison",
        {
            "official_basis": OFFICIAL_TUTORIAL_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "question": question,
            "experiments": experiments,
            "completion_rule": "比较 chunk 数、top-k 命中内容、噪声与 token 成本，不只看一个参数。",
        },
    )


if __name__ == "__main__":
    main()
