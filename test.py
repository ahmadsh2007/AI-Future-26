import time
from sentence_transformers import CrossEncoder

model = CrossEncoder("BAAI/bge-reranker-v2-m3", device="mps", max_length=512)
query = "What is the refund policy for international orders?"
chunks = ["Some sample passage of about 400 words... " * 40] * 30  # 30 chunks of realistic length

model.predict([(query, c) for c in chunks[:5]])  # warm-up run, not timed
start = time.time()
model.predict([(query, c) for c in chunks], batch_size=16)
print(f"Reranked 30 chunks in {time.time() - start:.2f}s")
