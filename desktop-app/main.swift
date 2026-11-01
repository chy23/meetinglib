import Cocoa
import PDFKit
import Foundation
import UserNotifications

// MARK: - 常數與設定管理
struct AppConfig {
    static let defaults = UserDefaults.standard
    static let defaultGdrivePath = "/Users/chiahua/Google 雲端硬碟/會議資料庫"
    static let websiteUrl = "https://chy23.github.io/meetinglib/"
    
    static var gdrivePath: String {
        get { defaults.string(forKey: "gdrivePath") ?? defaultGdrivePath }
        set { defaults.set(newValue, forKey: "gdrivePath") }
    }
    
    static var projectRoot: String {
        let appBundlePath = Bundle.main.bundlePath
        let scriptDir = (appBundlePath as NSString).deletingLastPathComponent
        // 如果是在 desktop-app/ 目錄下編譯運行，上一層即為專案根目錄
        let possibleRoot = (scriptDir as NSString).deletingLastPathComponent
        if FileManager.default.fileExists(atPath: "\(possibleRoot)/data/index.json") {
            return possibleRoot
        }
        // 預設固定路徑
        return "/Users/chiahua/.gemini/antigravity/scratch/meetinglib"
    }
}

// MARK: - 檔案拖曳與放置視圖 (Drag & Drop View)
class DropZoneView: NSView {
    var onFileDropped: ((URL) -> Void)?
    private var isHighlighted = false
    
    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
        layer?.cornerRadius = 12
        layer?.borderWidth = 2
        layer?.borderColor = NSColor.separatorColor.cgColor
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        guard let url = getUrl(from: sender), url.pathExtension.lowercased() == "pdf" else {
            return []
        }
        isHighlighted = true
        needsDisplay = true
        return .copy
    }
    
    override func draggingExited(_ sender: NSDraggingInfo?) {
        isHighlighted = false
        needsDisplay = true
    }
    
    override func prepareForDragOperation(_ sender: NSDraggingInfo) -> Bool {
        return true
    }
    
    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        isHighlighted = false
        needsDisplay = true
        if let url = getUrl(from: sender) {
            onFileDropped?(url)
            return true
        }
        return false
    }
    
    private func getUrl(from info: NSDraggingInfo) -> URL? {
        guard let board = info.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: nil) as? [URL],
              let url = board.first else { return nil }
        return url
    }
    
    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        if isHighlighted {
            layer?.borderColor = NSColor.systemBlue.cgColor
            layer?.backgroundColor = NSColor.systemBlue.withAlphaComponent(0.1).cgColor
        } else {
            layer?.borderColor = NSColor.separatorColor.cgColor
            layer?.backgroundColor = NSColor.windowBackgroundColor.withAlphaComponent(0.4).cgColor
        }
    }
}

// MARK: - 上傳發布懸浮視窗控制器
class PublishWindowController: NSWindowController {
    private var selectedFileUrl: URL?
    private var dateField: NSTextField!
    private var titleField: NSTextField!
    private var fileLabel: NSTextField!
    private var statusLabel: NSTextField!
    private var progressIndicator: NSProgressIndicator!
    private var publishButton: NSButton!
    private var gdriveCheckbox: NSButton!
    private var dropZone: DropZoneView!
    
    convenience init() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 460, height: 440),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "📤 發布會議紀錄至雙平台"
        window.isReleasedWhenClosed = false
        window.center()
        self.init(window: window)
        setupUI()
    }
    
    private func setupUI() {
        guard let contentView = window?.contentView else { return }
        
        // 1. 拖曳區域
        dropZone = DropZoneView(frame: NSRect(x: 20, y: 260, width: 420, height: 140))
        dropZone.onFileDropped = { [weak self] url in
            self?.handleFileSelected(url)
        }
        contentView.addSubview(dropZone)
        
        let dropIcon = NSTextField(labelWithString: "📄")
        dropIcon.font = NSFont.systemFont(ofSize: 36)
        dropIcon.alignment = .center
        dropIcon.frame = NSRect(x: 0, y: 75, width: 420, height: 44)
        dropZone.addSubview(dropIcon)
        
        fileLabel = NSTextField(labelWithString: "將 PDF 檔案拖曳至此處，或點下方按鈕選取")
        fileLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        fileLabel.textColor = .secondaryLabelColor
        fileLabel.alignment = .center
        fileLabel.frame = NSRect(x: 10, y: 40, width: 400, height: 24)
        dropZone.addSubview(fileLabel)
        
        let browseBtn = NSButton(title: "瀏覽本機檔案...", target: self, action: #selector(browseFile))
        browseBtn.frame = NSRect(x: 150, y: 12, width: 120, height: 26)
        browseBtn.bezelStyle = .rounded
        dropZone.addSubview(browseBtn)
        
        // 2. 會議日期輸入
        let dateLabel = NSTextField(labelWithString: "會議日期 (YYYY-MM-DD)：")
        dateLabel.frame = NSRect(x: 22, y: 215, width: 170, height: 20)
        dateLabel.font = NSFont.systemFont(ofSize: 13, weight: .bold)
        contentView.addSubview(dateLabel)
        
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd"
        dateField = NSTextField(string: dateFormatter.string(from: Date()))
        dateField.frame = NSRect(x: 195, y: 212, width: 245, height: 24)
        contentView.addSubview(dateField)
        
        // 3. 會議名稱輸入
        let titleLabel = NSTextField(labelWithString: "會議名稱 (如 教師午會記錄)：")
        titleLabel.frame = NSRect(x: 22, y: 175, width: 170, height: 20)
        titleLabel.font = NSFont.systemFont(ofSize: 13, weight: .bold)
        contentView.addSubview(titleLabel)
        
        titleField = NSTextField(string: "教師午會記錄")
        titleField.frame = NSRect(x: 195, y: 172, width: 245, height: 24)
        contentView.addSubview(titleField)
        
        // 4. 同步選項
        gdriveCheckbox = NSButton(checkboxWithTitle: "同步存檔至 Google 雲端硬碟 (會議資料庫)", target: nil, action: nil)
        gdriveCheckbox.state = .on
        gdriveCheckbox.frame = NSRect(x: 22, y: 135, width: 350, height: 20)
        contentView.addSubview(gdriveCheckbox)
        
        // 5. 進度條與狀態文字
        progressIndicator = NSProgressIndicator(frame: NSRect(x: 22, y: 95, width: 418, height: 16))
        progressIndicator.isIndeterminate = false
        progressIndicator.minValue = 0
        progressIndicator.maxValue = 100
        progressIndicator.isHidden = true
        contentView.addSubview(progressIndicator)
        
        statusLabel = NSTextField(labelWithString: "等待選擇檔案...")
        statusLabel.font = NSFont.systemFont(ofSize: 12)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.frame = NSRect(x: 22, y: 70, width: 418, height: 20)
        contentView.addSubview(statusLabel)
        
        // 6. 按鈕列
        publishButton = NSButton(title: "🚀 一鍵發布與推播部署", target: self, action: #selector(startPublish))
        publishButton.frame = NSRect(x: 250, y: 20, width: 190, height: 36)
        publishButton.bezelStyle = .rounded
        publishButton.keyEquivalent = "\r"
        publishButton.isEnabled = false
        contentView.addSubview(publishButton)
        
        let cancelBtn = NSButton(title: "關閉", target: self, action: #selector(closeWindow))
        cancelBtn.frame = NSRect(x: 160, y: 20, width: 80, height: 36)
        cancelBtn.bezelStyle = .rounded
        contentView.addSubview(cancelBtn)
    }
    
    @objc private func browseFile() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.pdf]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        if panel.runModal() == .OK, let url = panel.url {
            handleFileSelected(url)
        }
    }
    
    private func handleFileSelected(_ url: URL) {
        selectedFileUrl = url
        fileLabel.stringValue = "✅ 已選取: \(url.lastPathComponent)"
        fileLabel.textColor = .labelColor
        publishButton.isEnabled = true
        statusLabel.stringValue = "準備就緒，請核對上方日期與名稱後點擊發布"
        
        // 智慧解析檔名：例如 2026-11-04_教師午會記錄.pdf
        let filename = (url.deletingPathExtension().lastPathComponent)
        let regex = try? NSRegularExpression(pattern: #"^(\d{4}-\d{2}-\d{2})_(.+)$"#)
        if let match = regex?.firstMatch(in: filename, range: NSRange(location: 0, length: filename.utf16.count)) {
            if let dateRange = Range(match.range(at: 1), in: filename) {
                dateField.stringValue = String(filename[dateRange])
            }
            if let titleRange = Range(match.range(at: 2), in: filename) {
                titleField.stringValue = String(filename[titleRange])
            }
        }
    }
    
    @objc private func closeWindow() {
        window?.close()
    }
    
    @objc private func startPublish() {
        guard let fileUrl = selectedFileUrl else { return }
        let dateStr = dateField.stringValue.trimmingCharacters(in: .whitespaces)
        let titleStr = titleField.stringValue.trimmingCharacters(in: .whitespaces)
        
        if dateStr.isEmpty || titleStr.isEmpty {
            let alert = NSAlert()
            alert.messageText = "資料不完整"
            alert.informativeText = "請務必填寫會議日期與名稱！"
            alert.runModal()
            return
        }
        
        publishButton.isEnabled = false
        progressIndicator.isHidden = false
        progressIndicator.doubleValue = 15
        statusLabel.stringValue = "正在透過 Apple PDFKit 毫秒級提取全文內容..."
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            // 1. 原生 PDFKit 提取全文
            guard let pdfDoc = PDFDocument(url: fileUrl), let rawText = pdfDoc.string else {
                DispatchQueue.main.async {
                    self?.statusLabel.stringValue = "❌ PDF 文字解析失敗"
                    self?.publishButton.isEnabled = true
                }
                return
            }
            
            // 寫入臨時文字檔供 Python 引擎分析
            let tmpTextPath = "/tmp/meeting_raw_text_\(UUID().uuidString).txt"
            try? rawText.write(toFile: tmpTextPath, atomically: true, encoding: .utf8)
            
            DispatchQueue.main.async {
                self?.progressIndicator.doubleValue = 40
                self?.statusLabel.stringValue = "正在進行個資安全脫敏與圖片抽取..."
            }
            
            // 2. 呼叫後端發布引擎
            let projectDir = AppConfig.projectRoot
            let enginePath = "\(projectDir)/desktop-app/publisher_engine.py"
            var gdriveArg = ""
            if self?.gdriveCheckbox.state == .on {
                let gdrive = AppConfig.gdrivePath
                // 確保雲端資料夾存在
                try? FileManager.default.createDirectory(atPath: gdrive, withIntermediateDirectories: true)
                gdriveArg = "--gdrive \"\(gdrive)\""
            }
            
            let command = "python3 \"\(enginePath)\" --publish \"\(fileUrl.path)\" --date \"\(dateStr)\" --title \"\(titleStr)\" --text-file \"\(tmpTextPath)\" \(gdriveArg)"
            
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/zsh")
            process.arguments = ["-c", command]
            
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            
            do {
                try process.run()
                process.waitUntilExit()
                
                let outputData = pipe.fileHandleForReading.readDataToEndOfFile()
                let outputStr = String(data: outputData, encoding: .utf8) ?? ""
                try? FileManager.default.removeItem(atPath: tmpTextPath)
                
                DispatchQueue.main.async {
                    if process.terminationStatus == 0 {
                        self?.progressIndicator.doubleValue = 100
                        self?.statusLabel.stringValue = "🎉 發布大成功！雙平台已同步更新。"
                        
                        // 發送 macOS 系統通知
                        AppDelegate.showNotification(
                            title: "📚 會議紀錄發布成功！",
                            message: "【\(dateStr) \(titleStr)】已同步至 Google 雲端硬碟，並於 GitHub Pages 網站完成推播部署！"
                        )
                        
                        // 2.5 秒後自動關閉視窗
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                            self?.window?.close()
                            AppDelegate.shared.updateStatusMenu()
                        }
                    } else {
                        self?.statusLabel.stringValue = "⚠️ 發布過程發生錯誤，請檢查終端或網路。"
                        self?.publishButton.isEnabled = true
                        print("Error: \(outputStr)")
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    self?.statusLabel.stringValue = "執行失敗: \(error.localizedDescription)"
                    self?.publishButton.isEnabled = true
                }
            }
        }
    }
}

// MARK: - 主應用程式代理 (Menu Bar 狀態列控制器)
class AppDelegate: NSObject, NSApplicationDelegate {
    static var shared: AppDelegate!
    private var statusItem: NSStatusItem!
    private var publishWinController: PublishWindowController?
    private var statusMenuItem: NSMenuItem!
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        AppDelegate.shared = self
        
        // 請求 macOS 推播通知權限
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
        
        // 建立狀態列圖示 (NSStatusBar Item)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.title = "📚"
            button.toolTip = "會議資料庫發布小秘書"
        }
        
        setupMenu()
        updateStatusMenu()
    }
    
    private func setupMenu() {
        let menu = NSMenu()
        
        // 標題列
        let headerItem = NSMenuItem(title: "🏛️ 會議資料庫發布小秘書", action: nil, keyEquivalent: "")
        headerItem.isEnabled = false
        menu.addItem(headerItem)
        
        statusMenuItem = NSMenuItem(title: "狀態: 正在載入...", action: nil, keyEquivalent: "")
        statusMenuItem.isEnabled = false
        menu.addItem(statusMenuItem)
        menu.addItem(NSMenuItem.separator())
        
        // 核心發布與同步動作
        let uploadItem = NSMenuItem(title: "📤 拖曳／選取會議 PDF 發布...", action: #selector(openPublishWindow), keyEquivalent: "u")
        uploadItem.target = self
        menu.addItem(uploadItem)
        
        let syncItem = NSMenuItem(title: "🔄 立即雙向同步 (Google Drive ↔ GitHub)", action: #selector(triggerSync), keyEquivalent: "s")
        syncItem.target = self
        menu.addItem(syncItem)
        menu.addItem(NSMenuItem.separator())
        
        // 快捷連結
        let webItem = NSMenuItem(title: "🌐 開啟會議圖書館網站 (GitHub Pages)", action: #selector(openWebsite), keyEquivalent: "")
        webItem.target = self
        menu.addItem(webItem)
        
        let gdriveItem = NSMenuItem(title: "📁 開啟 Google 雲端硬碟本機資料夾", action: #selector(openGdriveFolder), keyEquivalent: "")
        gdriveItem.target = self
        menu.addItem(gdriveItem)
        
        let projectItem = NSMenuItem(title: "📂 開啟會議資料庫專案目錄", action: #selector(openProjectFolder), keyEquivalent: "")
        projectItem.target = self
        menu.addItem(projectItem)
        menu.addItem(NSMenuItem.separator())
        
        // 偏好設定與離開
        let prefItem = NSMenuItem(title: "⚙️ 偏好設定...", action: #selector(openPreferences), keyEquivalent: ",")
        prefItem.target = self
        menu.addItem(prefItem)
        
        menu.addItem(NSMenuItem(title: "🚪 結束發布小秘書", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        
        statusItem.menu = menu
    }
    
    func updateStatusMenu() {
        let indexPath = "\(AppConfig.projectRoot)/data/index.json"
        var count = 0
        var latest = "無"
        if let data = try? Data(contentsOf: URL(fileURLWithPath: indexPath)),
           let json = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] {
            count = json.count
            if let first = json.first, let d = first["date"] as? String, let t = first["title"] as? String {
                latest = "\(d) \(t)"
            }
        }
        statusMenuItem.title = "狀態: 就緒 (已收錄 \(count) 份｜最新: \(latest))"
    }
    
    @objc private func openPublishWindow() {
        if publishWinController == nil {
            publishWinController = PublishWindowController()
        }
        publishWinController?.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    @objc private func triggerSync() {
        statusItem.button?.title = "⏳"
        let projectDir = AppConfig.projectRoot
        let enginePath = "\(projectDir)/desktop-app/publisher_engine.py"
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/zsh")
            process.arguments = ["-c", "python3 \"\(enginePath)\" --sync"]
            try? process.run()
            process.waitUntilExit()
            
            DispatchQueue.main.async {
                self?.statusItem.button?.title = "📚"
                self?.updateStatusMenu()
                AppDelegate.showNotification(
                    title: "🔄 雙向同步完成",
                    message: "已自 Google Drive 索引及 GitHub 完成同步更新！"
                )
            }
        }
    }
    
    @objc private func openWebsite() {
        if let url = URL(string: AppConfig.websiteUrl) {
            NSWorkspace.shared.open(url)
        }
    }
    
    @objc private func openGdriveFolder() {
        let path = AppConfig.gdrivePath
        try? FileManager.default.createDirectory(atPath: path, withIntermediateDirectories: true)
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }
    
    @objc private func openProjectFolder() {
        NSWorkspace.shared.open(URL(fileURLWithPath: AppConfig.projectRoot))
    }
    
    @objc private func openPreferences() {
        let alert = NSAlert()
        alert.messageText = "⚙️ 偏好設定"
        alert.informativeText = "目前 Google 雲端硬碟同步路徑：\n\(AppConfig.gdrivePath)\n\n線上網站發布網址：\n\(AppConfig.websiteUrl)"
        alert.addButton(withTitle: "確定")
        alert.addButton(withTitle: "變更 Google 雲端路徑...")
        
        let response = alert.runModal()
        if response == .alertSecondButtonReturn {
            let panel = NSOpenPanel()
            panel.canChooseFiles = false
            panel.canChooseDirectories = true
            panel.allowsMultipleSelection = false
            panel.prompt = "選擇同步資料夾"
            if panel.runModal() == .OK, let url = panel.url {
                AppConfig.gdrivePath = url.path
            }
        }
    }
    
    static func showNotification(title: String, message: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = message
        content.sound = .default
        
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request, withCompletionHandler: nil)
    }
}

// 程式進入點
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
