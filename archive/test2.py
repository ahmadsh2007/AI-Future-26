import time, ollama

chunk = "Some sample passage of about 400 words... " * 40
batch = [chunk] * 50

for model in ["nomic-embed-text", "mxbai-embed-large", "qwen3-embedding:0.6b", "bge-m3"]:
    ollama.embed(model=model, input=batch[:2])  # warm-up
    start = time.time()
    ollama.embed(model=model, input=batch)
    rate = 50 / (time.time() - start)
    print(f"{model}: {rate:.1f} chunks/sec, 50k chunks ≈ {50000 / rate / 60:.0f} min")
