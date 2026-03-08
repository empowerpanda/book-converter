# 用 Render 部署「書籍轉換工具」網頁版

專案已設定好可在 **Render** 上跑（上傳 .epub → 轉換 → 下載）。Render 對 Python/Flask 支援穩定，用 `requirements.txt` 即可，無需額外設定。

---

## 一、前置：程式碼已在 GitHub

請確認專案已推送到 GitHub（例如：`https://github.com/empowerpanda/book-converter`）。

---

## 二、在 Render 建立 Web Service

### 方式 A：用 Blueprint（推薦，一鍵套用）

1. 登入 [Render](https://render.com)，用 GitHub 登入。
2. 點 **New +** → **Blueprint**。
3. 連到你的 GitHub repo（例如 `empowerpanda/book-converter`）。
4. Render 會讀取根目錄的 `render.yaml`，自動建立一個名為 `book-converter` 的 Web Service。
5. 點 **Apply**，等建置與部署完成（約 2–5 分鐘）。
6. 完成後會得到網址，例如：`https://book-converter-xxxx.onrender.com`。

### 方式 B：手動建立 Web Service

1. 登入 [Render](https://render.com)，點 **New +** → **Web Service**。
2. 選擇你的 GitHub repo（若未連過，先連接 GitHub 帳號）。
3. 設定：
   - **Name**：`book-converter`（或自訂）
   - **Region**：選離你較近的
   - **Branch**：`main`
   - **Runtime**：`Python 3`
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`gunicorn -b 0.0.0.0:$PORT app:app`
4. **Plan** 選 **Free**（免費方案即可）。
5. 點 **Create Web Service**，等部署完成。

---

## 三、部署後

- 首頁：`https://你的服務名.onrender.com/`
- 健康檢查：`https://你的服務名.onrender.com/api/health`（應回傳 `{"ok": true}`）

免費方案一段時間沒人使用會進入 sleep，下次打開時需等約 30–50 秒才會回應，屬正常現象。

---

## 四、之後更新

推送程式碼到 GitHub 的 `main` 分支後，Render 會自動重新建置並部署。

---

## 五、逾時與檔案大小（選用）

- 若轉換大書需要較久，可在 Render Dashboard：**Settings** → **Request timeout** 調高（例如 300 秒）。
- 本專案已限制上傳為 100 MB（在 `app.py`），一般 epub 足夠使用。
