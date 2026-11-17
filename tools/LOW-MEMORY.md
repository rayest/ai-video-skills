# 在 4GB 小服务器上跑 AI 视频流水线

背景：一台 2 核、3.7 GB 内存、没有 swap 的云服务器。4 天里系统 OOM killer 触发了 8 次：ffmpeg 涨到 1.3–1.9 GB、whisper 涨到 1.9–3.0 GB 时被杀，有一次还连带杀掉了 dbus。下面是之后定下的规则，按这些做以后没再崩过。

## mem-guard

`mem-guard [--max 2200M] [--wait] -- <命令>`

- 把命令放进带 `MemoryMax` 的 systemd scope：超了只杀这一个任务，不会波及其他进程；
- 全局锁：同一时间只跑一个重任务（`--wait` 排队，否则退出码 75）；
- 可用内存不够「上限 + 400 MB」就不启动。

退出码 137 表示任务超过上限：把任务改轻，不要调高上限。

安装：`install -m 755 tools/mem-guard ~/.local/bin/`（需要 systemd 和 flock）。

## ffmpeg

- 永远加 `-threads 2 -filter_threads 1`。**位置有讲究**：放在 `-i` 前面只限制解码器，编码器的 `-threads` 要放在所有输入之后。libx264 再加 `-x264-params threads=2:rc-lookahead=10:sync-lookahead=0`。参数放错位置时，一个 1080×1920 的编码进程 15 秒内从 250 MB 涨到 650 MB 以上。
- rawvideo 管道输入两边都用 `-threads 1`。
- preset 不要比 `medium` 更慢。
- 不要写一个很大的 `filter_complex`：分段渲染，再用 concat demuxer（`-f concat -c:v copy`）拼起来。

## Python 逐帧渲染（PIL / numpy）

- 从 ffmpeg 管道读一帧、画一帧、写一帧，绝不把帧存进列表。
- 超过约 20 秒就分块：每块 15 秒、各自一个受保护的进程，只输出视频，最后拼接再混音。这样不管视频多长，内存都是平的。
- 缓存整张图的 `lru_cache` 上限设在个位数。转场时尺寸每帧都变，不设上限会一直涨。
- 不要逐帧加随机噪点：压缩率会崩，20 MB 变 324 MB。

## 语音转写（faster-whisper）

- 默认用 `small` int8；`medium` 在 beam 5 下峰值约 2.1 GB。
- `cpu_threads=2`，`beam_size` ≤ 5，一个进程只加载一个模型。
- 多个片段先拼成一段再转写，或者分进程依次跑。

## 跑长任务之前

`free -m`、`df -h` 先看一眼；先跑 3–5 秒的试渲染，用 `/usr/bin/time -v` 看 Maximum resident set size。崩了先查 `journalctl -k | grep -E 'Killed process|memory cgroup'`，确认是谁、用了多少，再用更轻的配置重试。
