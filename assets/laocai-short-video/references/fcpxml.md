# FCPXML 编写、回写与兼容技巧

适用：将明确剪辑映射翻译为工程，或修改FCP最新回写。实测：FCP12.4、FCPXML1.14；历史 `templates/export_fcpxml.py` 为1.10示例，不是所有版本均可直接导入的保证。操作与交付见 [fcp-workflow.md](fcp-workflow.md)。

## 1. 结构、资源与媒体

```xml
<fcpxml version="1.14">
  <resources>
    <format id="r1" frameDuration="1/30s" width="1080" height="1920"
            colorSpace="1-1-1 (Rec. 709)"/>
    <asset id="rHost" name="主播实拍" start="0s" duration="300s"
           hasVideo="1" format="r1" hasAudio="1"
           audioSources="1" audioChannels="2" audioRate="48000">
      <media-rep kind="original-media" src="file:///绝对路径/host.mov"/>
    </asset>
  </resources>
  <library><event name="V新版本"><project name="审核项目">
    <sequence format="r1" duration="10s" tcStart="0s" tcFormat="NDF"
              audioLayout="stereo" audioRate="48k">
      <spine>
        <asset-clip ref="rHost" offset="0s" start="0s" duration="10s"
                    videoRole="主画面" audioRole="dialogue">
          <adjust-volume amount="-96dB"/>
        </asset-clip>
      </spine>
    </sequence>
  </project></event></library>
</fcpxml>
```

这是结构说明，不是脱离媒体即可运行的成片。资源id唯一，所有ref解析到资源，format和音视频元数据与真实素材对应；媒体路径用 `Path.as_uri()` 或正确的URL编码，不手工拼接未转义空格/中文。资产duration覆盖实际使用入出点。

用XML库序列化，避免手工字符串转义错误。子元素按当前版本DTD顺序插入；连接片段通常位于调整项之后、marker/filter/metadata之前，不能无脑append到metadata后。优先保持原生回写的结构与未修改字段，不做全文件“清理重写”。

新项目/事件不沿用旧对象uid和modDate，避免误更新旧版；资源身份与媒体引用无理由不改。原生回写会重编号ref，后续按对象身份、结构或名称筛选，不能永久硬编码 r9 就是水印。删除旧层后，只移除确认已无其他引用的资源。

## 2. 三种时间坐标与整数帧

项目帧、片段局部时间、素材源时间分别维护。帧范围用 `[first, end)`，duration为end-first。所有视觉切点在项目帧网上取整；音频采样时间保留必要精度，不把每个音频采样强制量化到视频帧。

```python
from fractions import Fraction

def frame_time(frame, fps=Fraction(30, 1)):
    t = Fraction(frame, 1) / fps
    return f'{t.numerator}/{t.denominator}s'
```

不能由浮点秒反复来回映射剪辑区间；本片曾因浮点逆映射边界误回到片尾，改成整数帧消除单帧错误。保持 `原片帧 → 累计删句后项目帧` 的唯一映射，字幕、小窗、动画共用。

- spine直属片段的offset在父sequence时间坐标中；start是该片段的源入点，二者**通常不同**。删句后全局时间不再等于原片时间。
- 连接片段offset使用**父片段的局部时间坐标**，不能统一当成项目全局时间，也不能简单忽略父start。未变速父片段可按 `child_offset = parent.start + (child_global - parent_global)` 理解；变速/嵌套情况需遵循父时间映射并用小样回写确认。
- 本片把整条包装、人声和连接层挂到首个start=0、项目起点=0的主播片段，所以这些连接offset数值恰好等于项目时间；这只是该结构的便利，不是通用规则。
- 连接层可超出父首片段持续时间，仍须验证整个sequence的最终覆盖。后续若移动或删除承载首片段，检查连接关系，必要时重挂稳定容器。

## 3. lane、role与静态PNG

主轨片段省略lane；连接层正lane位于主轨上方，音频可用负lane。使用 `asset-clip videoRole/audioRole`，`video role` 对应元素属性，不混写。role便于索引筛选，lane决定连接层位。本片示例：背景1、B-roll2、小窗3、图解4、字幕5、水印6；人声-1、音乐-2/-3。不是所有项目固定层位。

**本机PNG连接的兼容写法：**

```xml
<!-- resources中的静态图资源，format r1与项目画幅一致 -->
<asset id="rWM" name="水印白字" start="0s" duration="3600s"
       hasVideo="1" format="r1" videoSources="1">
  <media-rep kind="original-media" src="file:///绝对路径/水印白字.png"/>
</asset>
<!-- 插入父asset-clip中合法的位置 -->
<video ref="rWM" lane="6" offset="0s" start="0s"
       duration="10s" name="频道水印" role="水印"/>
```

静态PNG曾以 `<asset-clip>` 连接触发本机 `FFXMLImporter addAssetClip` SIGABRT，DTD仍通过；改 `<video>` 后成功。浏览器源素材事件可用 `<clip><video .../></clip>` 包装静态图。其他机器/版本不确定时先最小测试，不把这次崩溃推广为所有asset-clip都不能用。

透明PNG可做完整画幅，直接原点对齐。透明图解/字幕/同步小窗用ProRes4444保留alpha，分别引用；确认是真透明，而不是已经烧有黑底。FCP混合色彩空间可能导致PNG边缘与Pillow简单alpha混合不完全相同；预览和检查实际导出，不只拿理论像素等式判错。

## 4. 变速、定格与变换

变速用timeMap，timept的time为片段内部时间，value为素材绝对时间。定格是value不再增长，不能用0.02倍等极慢速度冒充。

```xml
<asset-clip ref="rBroll" offset="20s" start="0s" duration="2s"
            videoRole="产品素材">
  <timeMap>
    <timept time="0s" value="10s" interp="linear"/>
    <timept time="1s" value="21/2s" interp="linear"/>
    <timept time="2s" value="21/2s" interp="linear"/>
  </timeMap>
  <adjust-transform position="0 -3.12" scale="0.926 0.926"/>
</asset-clip>
```

实际生成统一Fraction。手写此种timeMap时start=0，入点放进首value；FCP原生回写可能将timept扩展到片段之外甚至负time，不用自己的简化表达强行改写它。检查有效片段内的映射，而不误删负time点。

position单位是项目画面高度的百分比，y向上为正：`x=dx/H*100`，`y=-dy/H*100`。scale与fit/conform及素材宽高比一起决定显示尺寸，不能只给一个scale就假设裁切准确。推近若原来以上方某锚点裁切，需要补偿位移，避免跳位；先用真实帧对比。

## 5. 原片静音与原生音量关键帧

本机导入/回写未可靠保留 `srcEnable="video"` 的排音效果。独立口播模式下，对仍带音频的实拍/B-roll额外设置 `adjust-volume amount="-96dB"`，并回写、导出确认无双份人声。-96dB是本机实用衰减方案，并非证明音频组件已删除。切勿误静音独立口播。

```xml
<adjust-volume>
  <param name="amount">
    <keyframeAnimation>
      <keyframe time="0s" value="-96dB"/>
      <keyframe time="1s" value="-12dB"/>
      <keyframe time="4s" value="-12dB"/>
      <keyframe time="5s" value="-96dB"/>
    </keyframeAnimation>
  </param>
</adjust-volume>
```

此音量示例为start=0；本片音量关键帧time采用**素材时间**，第二段音乐start=1804/15s时首关键帧也是1804/15s，不把项目offset当素材时间。生成后用FCP回写核对time/value以及曲线实际作用范围。

keyframe value用dB，音量keyframe省略interp/curve；本机对音量interp报警忽略。不要据此去掉timeMap中有效的interp。同节拍循环的两段音乐重叠，配合等功率交叉淡化；本片实际回写保留871个音乐关键帧。无需为所有项目制造同样数量，采样密度由包络与可编辑性决定。

## 6. 色彩、DTD与导入诊断

项目设置以实际目标为准，录音豆为Rec.709。原生回写曾有素材format的 `colorSpace="5-1-2"` 再导入报警；V12针对该问题改为已验证的 `1-1-1 (Rec. 709)`，并对相关镜头比对无可见变化。不能把真实HLG/PQ素材一律标成709来“修复”；元数据标记不等于色调映射，素材解释须核实。

用安装应用中匹配XML版本的DTD校验；本机原路径校验曾出现实体解析错误，复制到临时目录解决，如DTD有依赖应一并保留，不能假定所有DTD都只需单文件。

```bash
# 先确认实际版本与该文件存在，再复制并校验
cp '/Applications/Final Cut Pro.app/Contents/Frameworks/Interchange.framework/Versions/A/Resources/FCPXMLv1_14.dtd' /tmp/FCPXMLv1_14.dtd
xmllint --noout --dtdvalid /tmp/FCPXMLv1_14.dtd '工程.fcpxml'
```

DTD检查语法、元素顺序和属性，不检查媒体内容、叠层效果、用户选择的导入库或导出音量。闪退时读用户日志并缩小到最小复现，不反复导完整失败XML。警告必须逐项读懂，不能把“忽略属性后成功”说成完全兼容。

## 7. 回写与差异验证

FCP当前版本可能输出 `.fcpxmld/Info.fcpxml`。先解析包内XML，再核对project/sequence、frameDuration与duration、资源路径、主镜头切点、timeMap、静音/增益、音量关键帧，以及独立层覆盖。修改以此回写为基线，不用早期生成脚本覆盖它。

例如替换水印：删除旧水印层，确认不再有旧层ref后移除孤立资源，加入两套PNG与分段video；回写核对所有段 `[first,end)` 连续、首帧0、尾帧目标帧数、无旧水印。然后检查成片切点前后帧和非修改区域，音频不变时对码流hash。XML“看起来正确”不替代最终导出。


## 8. 本机语音突显与导出延迟（2026-10-22实测）

用户反馈回声时，先查重复人声、源片静音和现有效果，再查原录音；看到单声道人声或多条波形不能直接判定为回声原因。左右内容相同的双声道转为mono不会产生一个延迟副本。

FCP12.4在独立mono口播启用语音突显65%后，原生回写为：`<audio-channel-source srcCh="1" role="dialogue.dialogue-1"><adjust-voiceIsolation amount="65"/></audio-channel-source>`，放在对应asset-clip内，保留原生顺序。只在人声组件使用，不对同时播放的BGM也叠加突显。65%是本片待听审参数，不是通用默认，更不能保证消除所有房间混响。

本片9个位置的成片波形相关测量发现处理后人声相对V12固定延迟36.125ms；在48k下为1734采样。最终将单条人声原生连接offset改为 `-289/8000s`，持续时间增加相同长度，并引用同源尾补0.1s的WAV，避免尾部越界。回写保留此负offset；最终AAC9处复测相对V12均0ms（16k测量分辨率）。这是本机本素材实测，不可对其他项目盲目提前36ms；每次以实际导出测量，检查首尾、口型与其他同步轨。

仅修音时可由FCP导出WAV混音母带，最终以原视频 `-c:v copy` 配新AAC；验证视频码流hash完全相同、音乐关键帧不变及最终音频同步，不需要反复重编码全画面。A/B应取同段并匹配响度，技术测量与用户主观听感分开报告。
