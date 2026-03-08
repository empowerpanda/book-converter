# 部署到 GitHub 與線上網頁

讓「網頁上傳 → 轉換 → 下載」跑在 GitHub 上（程式碼存於 GitHub），並可選部署到免費雲端讓大家透過瀏覽器使用。

---

## 一、把專案放到 GitHub

### 1. 在 GitHub 建立新倉庫

1. 登入 [GitHub](https://github.com)，點右上角 **+** → **New repository**
2. **Repository name**：例如 `book-converter` 或 `書籍轉換工具`
3. 選 **Public**，不要勾選 "Add a README"（專案裡已有）
4. 按 **Create repository**

### 2. 在本機初始化並推上去

在終端機進入專案目錄後執行：

```bash
cd /Users/pandah./Desktop/書籍轉換工具

# 初始化 Git
git init

# 加入所有檔案（.gitignore 會排除 .venv、上傳檔等）
git add .
git commit -m "Initial commit: 書籍轉換工具（簡體/英文→繁中 epub、網頁版）"

# 連到你的 GitHub 倉庫（請把 YOUR_USERNAME 和 REPO_NAME 改成你的）
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# 推上 GitHub（主分支名稱依你倉庫設定，常見為 main）
git branch -M main
git push -u origin main
```

之後若要更新：

```bash
git add .
git commit -m "更新說明"
git push
```

---

## 二、在雲端跑「網頁版」（免費）

程式碼在 GitHub 後，可接到免費主機讓網頁版 24 小時可連。推薦 **Render.com**（免費方案約 750 小時/月，無流量約 15 分鐘會休眠，下次開啟會冷啟動）。

### 使用 Render 部署

1. 前往 [Render](https://render.com) 並登入（可用 GitHub 登入）
2. **Dashboard** → **New** → **Web Service**
3. 選 **Build and deploy from a Git repository**，連到你的 **GitHub** 帳號，選剛建立的倉庫（例如 `book-converter`）
4. 設定：
   - **Name**：`book-converter`（或自訂）
   - **Runtime**：`Python 3`
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`gunicorn -w 1 -b 0.0.0.0:$PORT --timeout 600 app:app`
5. 選 **Free** 方案，按 **Create Web Service**
6. 等建置完成後，Render 會給一個網址，例如：  
   `https://book-converter.onrender.com`  
   用瀏覽器開啟即可上傳 .epub、轉換、下載。

若倉庫根目錄有 `render.yaml`，也可在 Render 選 **New** → **Blueprint**，連到同一個 GitHub 倉庫，會依 `render.yaml` 自動建立上述 Web Service。

### 注意

- **英文書轉繁中**會呼叫翻譯 API（需網路），在 Render 上可正常使用。
- 免費方案單次請求逾時約 10 分鐘，若書很厚可考慮縮小單檔或改用付費方案。
- 上傳與轉換後的檔案僅暫存於主機，不會永久保存，下載後請自行保留。

---

## 三、只在 GitHub 放程式碼、自己本機跑網頁

若只想把程式碼放在 GitHub，不部署到雲端：

1. 照 **一** 的步驟把專案推上 GitHub。
2. 在自己電腦：
   ```bash
   git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
   cd REPO_NAME
   pip install -r requirements.txt
   python app.py
   ```
3. 瀏覽器開啟 http://127.0.0.1:5000 即可使用。

這樣「網頁上傳 → 自動轉換 → 下載」就建立在 GitHub 上，並可選擇是否用 Render 在網路上跑。
