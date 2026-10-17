# 🎮 GameScript Pro (通用遊戲獨立虛擬通道腳本工具)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**GameScript Pro** 是一款專為現代 Windows 遊戲與自動化操作設計的高效能、低延遲腳本引擎。結合直覺的**橫向 AOV 動作視覺化畫布**、**即時操作錄製**與**驅動級獨立訊號通道**（支援鍵盤、滑鼠以及真實 Xbox 360 虛擬手把），助您輕鬆構建與調試高精確度的自動化動作序列。

---

## 📑 目錄
- [專案簡介](#-專案簡介)
- [核心需求 (Requirements)](#-核心需求-requirements)
- [完整功能特性 (Features)](#-完整功能特性-features)
- [快速上手指南 (Quick Start)](#-快速上手指南-quick-start)
- [核心架構說明 (Architecture)](#-核心架構說明-architecture)
- [常見問題 (FAQ)](#-常見問題-faq)

---

## 🌟 專案簡介

傳統的連點或巨集工具通常缺乏直覺的流程視圖，且容易遭遇遊戲反作弊阻擋或後台遮擋問題。GameScript Pro 採用業界領先的軟硬體架構：
1. **視覺化工作流**：打破傳統代碼或流水清單限制，透過節點圖形化畫布直觀調整前後級順序、延遲與分支。
2. **多通道獨立虛擬通道**：從標準 API（SendInput）到後台句柄傳遞（PostMessage），再到真實核心驅動（Interception、ViGEmBus 虛擬搖桿），訊號穿透力強且安全穩定。
3. **即時零門檻錄製**：在遊戲中按下按鍵即時於畫布生成對應節點，自動優化合併按鍵時長，無多餘重複動作。

---

## 💻 核心需求 (Requirements)

### 1. 作業系統環境
* **作業系統**：Windows 10 / Windows 11 (64-bit 建議)
* **Python 環境**：Python 3.10 或更高版本
* **權限要求**：管理員權限（Administrator，用於驅動級訊號注入與全域鍵鼠監聽）

### 2. Python 依賴套件
* `PyQt6`：現代化響應式深色 GUI 介面
* `pynput`：全域按鍵與滑鼠事件監聽與即時捕捉
* `pywin32`：Windows 底層 Win32 API 視窗列舉與句柄交互
* `vgamepad`：ViGEmBus Xbox 虛擬手把 Python API
* `psutil`：進程過濾與視窗目標追蹤

### 3. 硬體 / 虛擬驅動組件 (依需求選配)
* **ViGEmBus (Virtual Gamepad Emulation Bus)**：
  * 用於模擬真實的 Xbox 360 控制器訊號（支援類比搖桿 LX/LY/RX/RY、按鈕 A/B/X/Y、扳機鍵 LT/RT）。
  * 專案內附安裝包位於 `assets/drivers/ViGEmBus_Setup.exe`。
* **Interception Driver**：
  * 核心驅動級鍵鼠訊號注入引擎，可繞過常見的遊戲軟體阻擋。
  * 專案內附安裝工具位於 `assets/drivers/interception_install.exe`。

---

## ⚡ 完整功能特性 (Features)

### 1. 橫向 AOV 動作視覺化畫布 (Node Graph Canvas)
* **深色科技網格窗格 (Dark Grid Canvas)**：提供 25px 窗格網格，視覺清晰具備高對比度。
* **節點醒目標記**：
  * **節點圓圈上直接標示按下按鍵**：`F`、`T`、`SPACE(␣)`、`ENTER(↵)`、`ESC`、`🖱左`、`🖱右`、`🎮A` 等，文字智慧置中縮放。
  * **節點下方清楚標記動作與時間**：第一行顯示動作名稱，第二行以高亮青藍色標明按下持續時間（如 `按下: 316ms`）。
* **智慧水平對齊與磁吸 (Smart Horizontal Snapping)**：
  * 新增節點時自動繼承前級節點 Y 高度，預設水平打直對齊。
  * 拖曳節點靠近其他節點 Y 軸（35px 內）時，自動強磁吸對齊，箭頭保證 100% 筆直無折彎。
  * 節點間距最佳化為 `220px`，徹底杜絕相鄰標籤文字重疊撞車。
* **自由互動與端口連線**：
  * 滑鼠按住輸出端口可直接拉出連線箭頭；後級節點輸入端口具備自動磁吸綠色光環。
  * 點選連線按 `Delete` 鍵即可隨時刪除箭頭；按住輸入孔向外拖曳亦可斷開連接。
  * 滑鼠中鍵按住拖曳可自由平移畫布（Pan），滾輪可即時放大縮小（Zoom 55% ~ 220%）。
* **一鍵智慧整隊 (🪄 Auto Layout)**：
  * 頂部工具列與右鍵選單皆支援「自動整隊」，自動去重、依序向右一字排開、全面拉直所有連線。

### 2. 即時動作錄製器 (Live Macro Recorder)
* **所見即所得（即時彈出節點）**：
  * 錄製中按下鍵盤按鍵瞬間，畫布立即彈出該節點；放開按鍵時原地即時刷新按住毫秒數（`key_hold_ms`）。
  * 畫布橫向捲軸自動跟隨錄製進度平滑右移。
* **智慧配對與優化**：
  * 成對的 KeyDown + KeyUp 自動無縫收束為單一 KeyClick，成對滑鼠 Down + Up 合併為 Single Click，避免節點數量暴增。
  * 停止錄製時絕不重複寫入，座標完全獨立排定，杜絕重疊與打結。

### 3. 多通道訊號注入引擎 (Input Engines)
* **SendInput**：Windows 標準底層鍵鼠 API，相容性最高、反應速度極快。
* **PostMessage**：後台視窗消息傳遞，即使視窗被遮擋或處於非啟動狀態亦能發送鍵鼠訊號。
* **Interception**：內核級驅動模式，直接與輸入驅動層對話。
* **ViGEmBus 虛擬手把**：直接向系統掛載虛擬 Xbox 360 控制器，適合需要搖桿推桿平滑輸入或僅支援手把操作的遊戲。

### 4. 流程邏輯控制
* **固定 / 隨機延時**：精準控制動作間隔，支援毫秒級隨機等待以模擬真人操作。
* **計時變數 X 雙輸出分支 (Counter Branch)**：
  * 支援設定計時器秒數或放開觸發。
  * 具備「⚡ 觸發動作」與「▶ 繼續動作」雙向分支流，輕鬆實現複雜連招與防卡判定。
* **無限循環 / 定次循環**：支援自訂循環次數與循環間隔。

---

## 🚀 快速上手指南 (Quick Start)

### 1. 安裝環境與依賴
確保已安裝 Python 3.10+，於專案根目錄開啟終端機（PowerShell 或 CMD）執行：

```powershell
pip install -r requirements.txt
```

### 2. (選用) 安裝手把 / 核心驅動
若需要模擬手把訊號或使用驅動級鍵盤滑鼠：
1. 進入 `assets/drivers/` 目錄。
2. 執行 `ViGEmBus_Setup.exe` 完成虛擬手把驅動安裝（無需重開機）。
3. 如需 Interception，以管理員身分執行 `interception_install.exe /install`（安裝後需重開機）。

### 3. 啟動程式
以管理員身分執行 `main.py`：

```powershell
python main.py
```

---

## 🧭 快捷鍵清單

| 快捷鍵 | 功能說明 |
| :--- | :--- |
| **Ctrl + F1** | 開始 / 停止目前巨集腳本回放 |
| **Ctrl + F2** | 開始 / 停止即時按鍵錄製 |
| **Delete** | 刪除選中的動作節點，或刪除選中的連線箭頭 |
| **滑鼠中鍵拖曳** | 平移自由節點畫布 (Pan) |
| **滑鼠滾輪** | 以滑鼠為中心放大 / 縮小畫布 (Zoom) |

---

## 🏛️ 核心架構說明 (Architecture)

```
GameScriptPro/
│── assets/                  # 靜態資源與第三方驅動安裝包
│   └── drivers/             # ViGEmBus 與 Interception 驅動
│── core/                    # 核心底層架構
│   │── input_engine/        # 輸入通道 (SendInput, PostMessage, Interception)
│   │── player.py            # 巨集播放器與排程引擎
│   │── recorder.py          # 智慧即時鍵鼠錄製器
│   │── vigem_engine.py      # Xbox 虛擬手把控制器介面
│   └── window_manager.py    # 視窗搜尋與句柄綁定管理
│── models/                  # 資料結構模型 (Macro, MacroNode, Profile)
│── storage/                 # JSON 設定檔與巨集持久化管理
│── ui/                      # PyQt6 視覺化圖形介面
│   │── dialogs/             # 動作設定、驅動管理、視窗挑選器對話框
│   │── panels/              # 編輯面板、工具箱、日誌面板
│   │── widgets/             # 橫向 AOV 畫布、磁吸節點 Widget
│   └── theme.py             # 深色高對比主題色彩配置
│── main.py                  # 應用程式進入點
│── build.spec               # PyInstaller 單一可執行檔打包設定
└── requirements.txt         # Python 依賴清單
```

---

## ❓ 常見問題 (FAQ)

**Q: 為什麼錄製時按鍵放開沒有立即出現？**  
A: GameScript Pro 具備智慧配對功能。當您按下按鍵時節點立即生成，當您放開按鍵時系統會即時更新精確的按住毫秒數（`key_hold_ms`），並原地刷新節點標籤，讓序列更加緊湊乾淨。

**Q: 畫布上的箭頭如果歪了，該如何拉直？**  
A: 您只需點擊頂部工具列的【🪄 自動整隊】按鈕，或在任意節點右鍵點選【🪄 水平打直對齊】，所有節點將自動水平對齊並維持 220px 理想間距，箭頭即刻完全打直。

**Q: 遊戲沒有接收到手把動作？**  
A: 請點擊主視窗左上角的【🛠️ 核心驅動】按鈕，確認 ViGEmBus 驅動狀態是否為已安裝。安裝驅動後即可正常模擬真實 Xbox 360 控制器。

---

## 📄 開源授權 (License)

本專案基於 [MIT License](LICENSE) 授權開源。
