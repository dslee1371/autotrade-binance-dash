# autotrade-binance-dash
autotrade-binance-dash


# autotrade-binance-dash

Python 기반의 AI 연동 Binance 선물 자동 트레이딩 시스템입니다.

## 🪪 License

This project is licensed under the [MIT License](LICENSE).

---

## ⚙️ 환경변수 설정 (.env)

자동 트레이딩 시스템의 동작을 위해 다음 환경변수를 설정해야 합니다. 민감한 정보는 `.env` 파일에 저장하고 `git` 커밋에서 제외해야 합니다 (`.gitignore`에 추가 필요).

```env
BINANCE_API_KEY="kd..."
BINANCE_SECRET_KEY="zKL..."
# ✅ MySQL 연결
MYSQL_USER=user1
MYSQL_PASSWORD=P%40ssw0rd                 # Streamlit에서 URL 인코딩된 비밀번호 사용 시

** 주의 사항 ** 따옴표(")를 사용하면 오류 발생
```

### 환경변수으로 스크릿 만들기
```
kubectl create secret generic autotrade-binance-dash-secret \
  --from-env-file=.env \
  -n coinauto
```

## 도커 이미지 만들기
```
# 도커 이미지 빌드
docker build -t autotrade-binance-dash:v0.1 .

# 도커 태크
docker tag autotrade-binance-dash:v0.1 172.10.30.11:5000/auto-coin/autotrade-binance-dash:v0.1

# 도커 푸쉬
docker push 172.10.30.11:5000/auto-coin/autotrade-binance-dash:v0.1
```

## Menifests
```
# ───────────────────────────────────────────────────────────
# Deployment
# ───────────────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autotrade-binance-dash
  namespace: coinauto
  labels:
    app: autotrade-binance-dash
spec:
  replicas: 1
  selector:
    matchLabels:
      app: autotrade-binance-dash
  template:
    metadata:
      labels:
        app: autotrade-binance-dash
    spec:
      containers:
        - name: autotrade-binance-dash
          image: 172.10.30.11:5000/auto-coin/autotrade-binance-dash:v0.1
          imagePullPolicy: IfNotPresent
          envFrom:
            - secretRef:
                name: autotrade-binance-dash-secret
---
# ───────────────────────────────────────────────────────────
# Service
# ───────────────────────────────────────────────────────────
apiVersion: v1
kind: Service
metadata:
  name: autotrade-binance-dash
  namespace: coinauto
spec:
  type: ClusterIP
  selector:
    app: autotrade-binance-dash
  ports:
    - name: http
      protocol: TCP
      port: 80
      targetPort: 8501
---
# ───────────────────────────────────────────────────────────
# Ingress
# ───────────────────────────────────────────────────────────
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: autotrade-binance-dash
  namespace: coinauto
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
    - host: autotrade-dash.apps.lab3.dslee.lab
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: autotrade-binance-dash
                port:
                  number: 80

```

## 배포하기
```
kubectl create -f menifests.yaml
```

