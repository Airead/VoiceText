# NSGlassEffectView — Liquid Glass API Reference

Apple's Liquid Glass design (macOS 26+) — 折射+反射+流体动画，替代传统 NSVisualEffectView 的静态模糊。

## 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `contentView` | NSView | 内容嵌入点，AppKit 自动处理文字可读性。**只有 contentView 内的内容保证正确渲染**，任意 subview 可能 z-order 异常 |
| `cornerRadius` | CGFloat | 一等属性，直接设圆角，不需要 maskImage hack |
| `tintColor` | NSColor | 背景着色，建议 alpha 0.2-0.3 |
| `style` | `.regular` / `.clear` | regular 通用；clear 仅用于媒体密集内容上方 |

## 基本用法

```swift
let glass = NSGlassEffectView(frame: rect)
glass.cornerRadius = 20
glass.style = .regular
glass.tintColor = NSColor.systemBlue.withAlphaComponent(0.3)
glass.contentView = myView

// NSPanel/NSWindow 必须设 clear 背景，否则窗口背景遮住 glass
window.backgroundColor = .clear
window.contentView = glass
```

### PyObjC 用法

```python
from AppKit import NSGlassEffectView

glass = NSGlassEffectView.alloc().initWithFrame_(frame)
glass.setCornerRadius_(18)
glass.setContentView_(webview)
```

## NSGlassEffectContainerView

多个 glass 元素的容器，控制液态融合效果。

| 属性 | 类型 | 说明 |
|------|------|------|
| `contentView` | NSView | 放置多个 NSGlassEffectView 的容器 view |
| `spacing` | CGFloat | glass 元素距离 < spacing 时自动液态合并 |

```swift
let container = NSGlassEffectContainerView(frame: rect)
container.spacing = 40.0
container.contentView = holderView  // holderView 包含多个 NSGlassEffectView
```

### 为什么需要 Container

- Glass 不能采样 glass — 多个独立 glass 元素叠加会视觉异常
- Container 内元素共享一个采样区域，保证一致性
- 性能更好（减少渲染 pass）

## NSGlassEffectView vs NSVisualEffectView

| | NSVisualEffectView | NSGlassEffectView |
|---|---|---|
| 最低版本 | macOS 10.10 | macOS 26 |
| 视觉效果 | 静态高斯模糊 | 动态折射+反射+流体动画 |
| 圆角 | 需要 `setMaskImage:` | 内置 `cornerRadius` 属性 |
| 内容嵌入 | `addSubview` | `contentView` 属性 |
| 多元素融合 | 不支持 | `NSGlassEffectContainerView` |
| tint | 靠 material 枚举 | `tintColor` 任意颜色 |

**NSVisualEffectView 在本项目中已废弃。** 新 panel 如需 blur 必须用 NSGlassEffectView，不需要 blur 的用普通 NSView。

## 锁定自适应外观（关键！）

NSGlassEffectView 默认持续采样背后内容亮度来自动切换 light/dark 渲染，忽略系统主题和 `setAppearance_`。必须用私有属性 `_adaptiveAppearance` 锁定：

| 值 | 含义 |
|----|------|
| 0 | 强制 Light |
| 1 | 强制 Dark |
| 2 | Auto（默认，根据背后内容亮度自适应） |

项目中已封装为 `configure_glass_appearance(glass)`（见 `ui_helpers.py`），所有 NSGlassEffectView 实例必须调用：

```python
from wenzi.ui_helpers import configure_glass_appearance

glass = NSGlassEffectView.alloc().initWithFrame_(frame)
glass.setCornerRadius_(12)
configure_glass_appearance(glass)
```

来源：[qt-liquid-glass](https://github.com/fsalinas26/qt-liquid-glass) 逆向发现，私有 API 需 `respondsToSelector_` 保护。

### 其他私有属性

| 属性 | 值 | 说明 |
|------|-----|------|
| `_variant` | 0-23 | 材质变体（2=dock, 9=通知中心, 16=sidebar） |
| `_scrimState` | 0/1/2 | 遮罩层（0=无, 1=light, 2=dark） |
| `_subduedState` | 0/1 | 降低饱和度 |
| `_contentLensing` | int | 折射强度 |
| `_interactionState` | 0/1 | 悬停高亮（≥2 会 crash） |

## 性能注意

- GPU 开销显著高于 NSVisualEffectView
- Apple 建议限制 5-10 个 glass 元素
- 频繁 show/hide 或高频重绘场景（如 recording indicator 20Hz）需评估

## 已迁移的 Panel

- Recording indicator — `recording_indicator.py:_make_glass_view()`
- Streaming overlay — `streaming_overlay.py`
- Chooser panel — `chooser_panel.py:_build_panel()`

## 参考资料

- [NSGlassEffectView — Apple Developer](https://developer.apple.com/documentation/appkit/nsglasseffectview)
- [NSGlassEffectContainerView — Apple Developer](https://developer.apple.com/documentation/appkit/nsglasseffectcontainerview)
- [WWDC25 Session 310 — Build an AppKit app with the new design](https://developer.apple.com/videos/play/wwdc2025/310/)
- [Xcode 26 Liquid Glass 实现指南](https://github.com/artemnovichkov/xcode-26-system-prompts/blob/main/AdditionalDocumentation/AppKit-Implementing-Liquid-Glass-Design.md)
- [NSWindow glass 圆角实践](https://github.com/onmyway133/blog/issues/1025)
