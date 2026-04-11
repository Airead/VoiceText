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

NSGlassEffectView 默认持续采样背后内容亮度来自动切换 light/dark 渲染，忽略系统主题和 `setAppearance_`。在 macOS 26 上，需要用私有属性 `_adaptiveAppearance` **关闭**自适应，再用 `setAppearance_` 指定 light/dark：

| 值 | 含义 |
|----|------|
| 0 | automatic |
| 1 | off |
| 2 | on |

项目中已封装为 `configure_glass_appearance(glass)`（见 `ui_helpers.py`），所有 NSGlassEffectView 实例必须调用：

```python
from wenzi.ui_helpers import configure_glass_appearance

glass = NSGlassEffectView.alloc().initWithFrame_(frame)
glass.setCornerRadius_(12)
configure_glass_appearance(glass)
```

说明：旧的逆向资料常把 `_adaptiveAppearance` 记成 `0=Light, 1=Dark, 2=Auto`，但这与 macOS 26 runtime inspection 不符。项目内验证结果是 `1=off`，这也是当前需要使用的值。私有 API 需 `respondsToSelector_` 保护。

### 其他私有属性

| 属性 | 值 | 说明 |
|------|-----|------|
| `_variant` | 0-23 | 材质变体（2=dock, 9=通知中心, 16=sidebar） |
| `_scrimState` | 0/1/2 | 遮罩层（0=无, 1=light, 2=dark） |
| `_subduedState` | 0/1 | 降低饱和度 |
| `_contentLensing` | int | 折射强度 |
| `_interactionState` | 0/1 | 悬停高亮（≥2 会 crash） |

## 最佳实践

### 始终使用 contentView

`NSGlassEffectView.contentView` 是 Apple 设计的内容嵌入点。只有放在 `contentView` 内的视图才能获得正确的 z-order 和文字可读性处理。用 `addSubview_` 直接加到 glass 上的视图可能在 glass 材质之下渲染，产生视觉异常。

```python
# ✓ 正确
glass.setContentView_(my_content_view)

# ✗ 避免 — 内容可能被 glass 材质遮挡
glass.addSubview_(my_content_view)
```

例外：纯装饰性 view（outline、highlight）可以用 `addSubview_` 加到 glass 上，因为它们本来就应该叠在材质之上。

### 启用 Layer 裁切

```python
glass.setWantsLayer_(True)
glass.layer().setMasksToBounds_(True)
```

这确保 glass 内部的子 view 和装饰层被裁切到圆角边界内，避免内容溢出到圆角之外。所有使用了装饰 subview 的 glass 面板都应该启用。

### 窗口配置

```python
panel.setOpaque_(False)
panel.setBackgroundColor_(NSColor.clearColor())
panel.setHasShadow_(True)
```

- `setOpaque_(False)` + `clearColor` 让 glass 的透明/折射效果能正确显示
- `setHasShadow_(True)` 提供浮起感，是 glass 面板视觉层次的重要组成部分

### 根据面板尺寸调整处理强度

| 面板类型 | 推荐处理 | 原因 |
|---------|---------|------|
| 紧凑型（indicator、alert pill） | outline + highlight band | 小面板容忍更强的视觉处理，需要更强的 glass 感知 |
| 内容型（streaming overlay、大面板） | 仅 outline，且更细更轻 | 装饰不能与文字内容竞争注意力 |
| 全尺寸（chooser、settings） | 仅 layer masking + shadow | 已经有足够的视觉重量，不需要额外装饰 |

## 增强 Glass 视觉效果的常见手法

### Outline（边缘轮廓）

在 glass 上叠加一个仅有 `borderWidth` 的透明 view，增强边缘清晰度，让 glass 更像悬浮的玻璃表面而不是模糊的半透明色块。

```python
from wenzi.ui_helpers import dynamic_color

ol_color = dynamic_color((1.0, 1.0, 1.0, 0.26), (1.0, 1.0, 1.0, 0.14))
outline = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
outline.setWantsLayer_(True)
outline.layer().setCornerRadius_(corner_radius)
outline.layer().setBorderWidth_(1.0)       # 紧凑面板用 1.0
outline.layer().setBorderColor_(ol_color.CGColor())
glass.addSubview_(outline)
```

**参数调节：**

| 面板类型 | borderWidth | light alpha | dark alpha |
|---------|-------------|-------------|------------|
| 紧凑型 | 1.0 | 0.26–0.30 | 0.14–0.16 |
| 内容型 | 0.5 | 0.20–0.22 | 0.08–0.10 |

### Highlight Band（高光带）

在 glass 上部叠加一个半透明白色矩形，模拟光线从上方照射到玻璃表面的高光反射。仅适用于紧凑的 pill/capsule 形状面板。

```python
hl_color = dynamic_color((1.0, 1.0, 1.0, 0.16), (1.0, 1.0, 1.0, 0.08))
highlight = NSView.alloc().initWithFrame_(
    NSMakeRect(1, h * 0.50, w - 2, h * 0.38)
)
highlight.setWantsLayer_(True)
highlight.layer().setBackgroundColor_(hl_color.CGColor())
highlight.layer().setCornerRadius_(h * 0.19)
glass.addSubview_(highlight)
```

**注意：** highlight 会覆盖在下方内容之上。在有动画内容（波形图等）或大量文字的面板上会显得突兀，应避免使用。目前仅 `wz.alert` pill 使用了 highlight band。

### tintColor（着色）

通过 `glass.setTintColor_()` 给 glass 材质叠加一层半透明色调。适合需要品牌色或状态色暗示的场景。

```python
glass.setTintColor_(NSColor.systemBlue().colorWithAlphaComponent_(0.25))
```

建议 alpha 0.2–0.3。过高会遮盖折射效果。

### Dynamic Color（动态颜色）

所有装饰用颜色都应使用 `dynamic_color()` 适配 light/dark 模式，避免硬编码：

```python
from wenzi.ui_helpers import dynamic_color

# light_rgba, dark_rgba — 分别指定两种模式下的颜色
color = dynamic_color((1.0, 1.0, 1.0, 0.26), (1.0, 1.0, 1.0, 0.14))
```

### 装饰 View 的事件穿透

装饰性 subview（outline、highlight）覆盖在 glass 上会拦截鼠标和滚轮事件。如果 glass 下方有需要交互的内容（文字选择、滚动），装饰 view 必须重写 `hitTest_` 返回 nil：

```python
class _PassthroughView(NSView):
    """装饰 view，不拦截任何事件。"""
    def hitTest_(self, point):
        return None
```

**何时需要：**
- `panel.setIgnoresMouseEvents_(True)` 的面板（如 indicator、alert）→ **不需要**，整个面板已忽略事件
- 包含可交互内容的面板（如 streaming overlay 的文字选择和滚动）→ **需要**

注意 PyObjC class name 全局唯一，不同模块需使用不同类名（如 `_OverlayOutlineView`、`_ChooserOutlineView`）。

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
