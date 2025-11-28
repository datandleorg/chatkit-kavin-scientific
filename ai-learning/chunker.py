from markdown_it import MarkdownIt

md = MarkdownIt()
tokens = md.parse(open("example.md", encoding="utf-8").read())

# Collect all matching chunks
chunks = []
for token in tokens:
    if token.type == "html_block" and token.content and not token.content.lstrip().startswith("<img"):
        chunks.append(token.content)

# Write chunks to file with a separator
with open("example_chunks.txt", "w", encoding="utf-8") as f:
    for i, chunk in enumerate(chunks):
        f.write(chunk)
        if i < len(chunks) - 1:
            f.write("\n---\n")
