# 用 Vercel 部署「書籍轉換工具」網頁版

專案已設定好可在 **Vercel** 上跑（上傳 .epub → 轉換 → 下載）。依下列步驟即可從 GitHub 部署到 Vercel。

---

## 一、前置：程式碼已在 GitHub

請確認專案已推送到 GitHub（例如：`https://github.com/empowerpanda/book-converter`）。  
若尚未推送，請先完成 [DEPLOY.md](DEPLOY.md) 的「一、把專案放到 GitHub」。

---

## 二、在 Vercel 建立專案並連到 GitHub

1. **登入 Vercel**  
   前往 [vercel.com](https://vercel.com)，用 **GitHub** 登入。

2. **匯入專案**  
   - 點 **Add New…** → **Project**  
   - 在列表中選 **empowerpanda/book-converter**（或你的 repo 名稱）  
   - 若沒出現，點 **Import Git Repository**，輸入 `empowerpanda/book-converter` 或貼上 repo 網址

3. **設定專案（通常不用改）**  
   - **Framework Preset**：選 **Other** 或 **Flask**（若有）  
   - **Root Directory**：留空（專案在根目錄）  
   - **Build Command**：可留空，Vercel 會依 `requirements.txt` 安裝依賴  
   - **Output Directory**：留空  
   - **Install Command**：可留空，或填 `pip install -r requirements.txt`

4. **部署**  
   點 **Deploy**，等幾分鐘。完成後會得到一個網址，例如：  
   `https://book-converter-xxxx.vercel.app`

5. **之後每次更新**  
   只要在本地 `git push` 到 GitHub，Vercel 會自動重新部署。

6. **函數逾時（選用）**  
   若轉換大書需要較長時間，可在 Vercel 專案 **Settings → Functions → Max Duration** 設為 60 秒（或更高）。專案以根目錄的 `app.py` 為 Flask 單一入口；`.vercelignore` 已排除 `pyproject.toml`，強制 Vercel 依 `requirements.txt` 安裝依賴（避免 uv/pyproject 路徑不裝套件的問題）。

---

## 三、本機用 Vercel CLI 部署（選用）

若想用指令部署而不用網頁：

```bash
# 安裝 Vercel CLI（若尚未安裝）
npm i -g vercel

cd /Users/pandah./Desktop/書籍轉換工具

# 登入並部署（會提示連結到現有專案或建立新專案）
vercel
```

依提示登入、選專案或新建，即可部署。之後要更新同樣執行 `vercel` 或透過 GitHub 自動部署。

---

## 四、注意事項（Vercel 限制）

- **分章轉換**：簡體書與英文書都會在瀏覽器內拆成章節，**每章各自呼叫 API**（每章 60 秒內完成），最後在瀏覽器組回一本 epub 下載，因此**大書也不受單次 60 秒限制**。
- **暫存**：上傳與轉換後的檔案只存在當次請求的暫存目錄（或僅在瀏覽器記憶體），不會永久保存，下載後請自行保留。
- **依賴與容量**：Vercel 會依 `requirements.txt` 安裝套件；若部署失敗，可在 Vercel 專案 **Settings → General** 檢查 **Install Command** 是否為 `pip install -r requirements.txt`。

---

## 五、若部署失敗可檢查

1. **Vercel 專案 Settings → General**  
   - **Install Command**：`pip install -r requirements.txt`  
   - **Build Command**：留空或依 Vercel 預設

2. **Vercel 專案 Settings → Functions**  
   - 確認 **Max Duration** 為 60 秒（或你設定的秒數）

3. **日誌**  
   在 Vercel 專案 **Deployments** 點進最新一次部署，看 **Building** / **Function Logs** 的錯誤訊息，多數是缺套件或逾時。

### 若出現 500 / FUNCTION_INVOCATION_FAILED

1. **先試健康檢查**  
   開啟 `https://你的網址/api/health`，若回傳 `{"ok": true}` 代表 Flask 有啟動，問題多半在首頁或轉換流程；若連這裡都 500，代表啟動階段就失敗。

2. **看詳細錯誤**  
   Vercel 專案 → **Logs**（或 Deployments → 該次部署 → **Functions** 的 log），會看到 Python traceback。常見原因：  
   - **Build 沒裝好依賴**：到 **Settings → General** 確認 **Install Command** 為 `pip install -r requirements.txt`，重新 Deploy。  
   - **寫入目錄失敗**：專案已改為寫入失敗時自動改用 `/tmp`，理論上可避免。  
   - **Python 版本**：專案已加 `.python-version`（3.12），若你曾改過設定可改回 3.12 再部署。

3. **本機用 Vercel 跑一次**  
   安裝 Vercel CLI 後在專案目錄執行 `vercel dev`，在本地用與 Vercel 相同環境跑，終端會印出錯誤原因。

完成以上步驟後，你的「書籍轉換工具」就會在 Vercel 上跑，並可透過 Vercel 給的網址使用網頁版。

---

## 六、綁定自己的網域（免費）

Vercel **免費方案就支援自訂網域**，不用加價。你買的網域可以直接掛在這個專案上。

### 步驟

1. **進專案設定**  
   在 Vercel 打開你的 **book-converter** 專案 → 上方 **Settings** → 左側 **Domains**。

2. **新增網域**  
   - 在 **Domain** 欄位輸入你的網域，例如：`books.yourdomain.com` 或 `yourdomain.com`  
   - 按 **Add**。

3. **照 Vercel 指示設定 DNS**  
   Vercel 會顯示要你加的一筆（或兩筆）紀錄，依你選的網域類型不同：

   - **子網域**（例如 `books.yourdomain.com`）  
     - 類型：**CNAME**  
     - 名稱：`books`（或你用的子網域）  
     - 目標：Vercel 會給一個值，例如 `cname.vercel-dns.com`  
     - 到你**買網域的地方**（GoDaddy、Cloudflare、Namecheap、Google Domains 等）的 DNS 管理頁，新增一筆 CNAME，照上面填。

   - **根網域**（例如 `yourdomain.com`）  
     - 通常會要你加 **A** 紀錄指到 Vercel 的 IP，或把 **Nameservers** 改成 Vercel 的。  
     - 畫面上會寫清楚要填什麼，照做即可。

4. **等生效**  
   DNS 生效大約 幾分鐘到 48 小時（多數幾十分鐘內）。  
   Vercel 的 **Domains** 頁會顯示狀態，變成綠勾就代表成功；若有問題會顯示錯誤說明。

5. **HTTPS**  
   綁好網域後，Vercel 會自動幫你申請 **免費 SSL（HTTPS）**，不用再付費或額外設定。

### 小提醒

- 一個專案可以加**多個網域**（例如 `books.yourdomain.com` 和 `convert.another.com`），都是免費。
- 若你有多個專案，每個專案都可以綁不同網域；你買的很多網域可以分別掛在不同 Vercel 專案上。
- 網域費用是你跟註冊商的事，Vercel **不跟你收「綁定網域」的錢**，只收你原本的 Vercel 方案（免費方案就夠用）。
