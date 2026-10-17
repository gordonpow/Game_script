# 驅動安裝檔存放目錄 (Assets Drivers)

此目錄用於放置打包進 EXE 的驅動安裝套件：
- `interception_install.exe`：Interception Driver 安裝程式 (可用指令 `install-interception.exe /install` 部署)
- `interception.dll`：Interception C API 動態函式庫 (x64 / x86)
- `ViGEmBus_Setup.msi` 或 `ViGEmBus_Setup_1.22.0_x64.exe`：ViGEmBus 官方安裝套件

當程式打包成單一 EXE 執行檔時，此目錄內容會自動封裝至內部臨時目錄；
使用者啟動「首次設定精靈」時即可一鍵觸發安裝。
