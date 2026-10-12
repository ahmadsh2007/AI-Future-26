import time
from sentence_transformers import CrossEncoder

model = CrossEncoder("BAAI/bge-reranker-base", device="mps", max_length=512)
query = "What is the refund policy for international orders?"
chunks = ["Some sample passage of about 400 words... " * 40] * 30  # 30 chunks of realistic length

for n in [30, 15]:
    times = []
    for _ in range(4):
        start = time.time()
        model.predict([(query, c) for c in chunks[:n]], batch_size=16)
        times.append(time.time() - start)
    print(f"{n} chunks: " + ", ".join(f"{t:.2f}s" for t in times))
