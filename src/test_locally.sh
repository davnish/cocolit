docker run --name inference-server -p 8000:8000 ghcr.io/davnish/inference-server:3e7d5d0

docker network create cocolit-network

# Connect the existing FastAPI container to the network
docker network connect cocolit-network inference-server


docker run -p 8501:8501 \
  --network cocolit-network \
  --env INFERENCE_URL=http://inference-server:8000/predict \
  streamlit-server:3e7d5d0