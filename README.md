# 庫存同步系統 (Inventory Sync System)

這是一個簡單的Flask網頁應用程式，用於同步您的官網庫存資料與供應商庫存資料。

## 功能特點

- 支援多個供應商資料格式 (目前支援 Light in the Attic 和 Juno)
- 自動比較並更新庫存數量
- 維護歷史記錄和差異報告
- 自動清理舊檔案 (預設7天)
- 同步處理「預購」和「現貨」SKU

## 資料夾結構

```
/
├── app.py                # 主要應用程式程式碼
├── start_app.sh          # 啟動腳本
├── templates/
│   └── index.html        # 網頁介面
├── uploaded_files/       # 暫存上傳的檔案
└── records/              # 儲存處理記錄和差異報告
```

## 使用方式

1. 執行 `./start_app.sh` 啟動應用程式
2. 在瀏覽器中開啟 http://localhost:5000
3. 選擇供應商 (Light in the Attic 或 Juno)
4. 上傳您的官網庫存檔案和供應商庫存檔案
5. 點擊「開始同步」按鈕
6. 系統將自動下載更新後的Excel檔案

## 技術細節

- 使用 Flask 建構網頁應用程式
- 使用 Pandas 處理和比較 Excel 資料
- 自動生成差異報告，方便追蹤變更
- 自動清理舊檔案，避免浪費空間

## 安裝步驟

1. 確保已安裝Python 3
2. 安裝相依套件：`pip install -r requirements.txt`
3. 給予啟動腳本執行權限：`chmod +x start_app.sh`
4. 執行啟動腳本：`./start_app.sh`

## 備註

這個應用程式是為了解決特定庫存管理問題而開發的，支援指定的Excel格式。如需支援其他格式或供應商，需要修改程式碼。