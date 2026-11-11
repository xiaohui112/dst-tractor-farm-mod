"""FMOD Designer 音频包结构检查（支持原生 RIFF FEV + FSB5 PCM）。"""
import hashlib
import struct

PROJECT = 'aom_irrigator_music'
EVENT = PROJECT + '/irrigator/lanhuacao'


def riff_chunks(data, start, end):
    chunks = {}
    while start < end:
        if start + 8 > end:
            raise ValueError('FEV 的 RIFF 块头不完整')
        tag, size = struct.unpack_from('<4sI', data, start)
        stop = start + 8 + size
        if stop > end:
            raise ValueError('FEV 的 RIFF 块被截断')
        payload = data[start + 8:stop]
        if tag == b'LIST':
            chunks.update(riff_chunks(data, start + 12, stop))
        else:
            chunks[tag] = payload
        start = stop + (size & 1)
    return chunks


def inspect_pair(fev, fsb):
    if len(fev) < 64 or len(fsb) < 64:
        raise ValueError('音频包不完整')
    if fev[:4] == b'RIFF':
        if fev[8:12] != b'FEV ' or struct.unpack_from('<I', fev, 4)[0] != len(fev) - 8:
            raise ValueError('RIFF FEV 标识或长度不正确')
        chunks = riff_chunks(fev, 12, len(fev))
        prop = chunks.get(b'PROP', b'')
        if len(prop) < 4 or prop[4:].rstrip(b'\0').decode() != PROJECT:
            raise ValueError('FEV 项目名称不正确')
        if not all(name.encode() + b'\0' in chunks.get(b'STRR', b'') for name in ('irrigator', 'lanhuacao')):
            raise ValueError('FEV 缺少目标事件分组/名称')
    elif fev[:4] != b'FEV1':
        raise ValueError('需要 FMOD Designer 的 FEV，不能使用 Studio .bank 或重命名的 WAV/MP3')
    if fsb[:4] not in (b'FSB3', b'FSB4', b'FSB5'):
        raise ValueError('需要 FMOD FSB3/4/5 采样库')
    info = {'event': EVENT, 'fev_sha256': hashlib.sha256(fev).hexdigest(),
            'fsb_sha256': hashlib.sha256(fsb).hexdigest()}
    if fsb[:4] == b'FSB5':
        version, count, headers, names, size, codec = struct.unpack_from('<6I', fsb, 4)
        base = 60 if version == 1 else 64
        if version not in (0, 1) or base + headers + names + size != len(fsb):
            raise ValueError('FSB5 采样库长度不正确或被截断')
        if fsb[36:44] not in fev:
            raise ValueError('FEV 与 FSB5 的编译校验值不匹配，需成对重建')
        if count == 1 and codec == 2 and headers == 8:
            word = struct.unpack_from('<Q', fsb, base)[0]
            rates = [4000, 8000, 11000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 96000]
            index = (word >> 1) & 15
            if index >= len(rates) or word & 1:
                raise ValueError('不支持的 FSB5 采样头')
            frames, channels, rate = word >> 34, ((word >> 5) & 1) + 1, rates[index]
            offset = base + headers + names + (((word >> 6) & 0xfffffff) * 32)
            pcm = fsb[offset:offset + frames * channels * 2]
            if len(pcm) != frames * channels * 2:
                raise ValueError('FSB5 PCM 数据不完整')
            info.update(frames=frames, channels=channels, rate=rate, duration=frames / rate,
                        pcm_sha256=hashlib.sha256(pcm).hexdigest())
    return info
