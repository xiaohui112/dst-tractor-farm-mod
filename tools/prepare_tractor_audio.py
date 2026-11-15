#!/usr/bin/env python3
"""Prepare the approved C work loop and music at native farm-plow sample loudness."""
from array import array
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path
import wave

ROOT=Path(__file__).resolve().parents[1]
AUDIO=ROOT/'assets/audio'
REFERENCE=AUDIO/'native-sfx-reference.json'


def measure(path, target=-15.54):
    result=subprocess.run(['ffmpeg','-hide_banner','-i',str(path),'-af',
        f'loudnorm=I={target}:TP=-3:LRA=11:print_format=json','-f','null','-'],
        capture_output=True,text=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',result.stderr,re.S)[0])


def normalize(source,destination,target,channels):
    info=measure(source,target)
    settings=f'loudnorm=I={target}:TP=-3:LRA=11'
    settings+=f':measured_I={info["input_i"]}:measured_TP={info["input_tp"]}'
    settings+=f':measured_LRA={info["input_lra"]}:measured_thresh={info["input_thresh"]}'
    settings+=f':offset={info["target_offset"]}:linear=true'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),
        '-af',settings,'-ar','44100','-ac',str(channels),'-c:a','pcm_s16le',str(destination)],check=True)
    return measure(destination,target)


def prepare():
    reference=json.loads(REFERENCE.read_text())
    target=reference['target_lufs']
    with tempfile.TemporaryDirectory(prefix='tractor-audio-') as temp:
        temp=Path(temp);decoded=temp/'decoded.wav'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',
            str(AUDIO/'sources/sfxmint-tractor-02.mp3'),'-ac','1','-ar','44100',
            '-c:a','pcm_s16le',str(decoded)],check=True)
        with wave.open(str(decoded),'rb') as f:
            rate=f.getframerate();pcm=array('h',f.readframes(f.getnframes()))
        # Circular overlap: end blends into the original head, followed by the
        # next sample after that head. No silence, start/end fades or pitch change.
        overlap=round(rate*.12)
        cross=array('h',(round(pcm[-overlap+i]*(1-i/overlap)+pcm[i]*(i/overlap)) for i in range(overlap)))
        loop=pcm[overlap:-overlap]+cross
        raw=temp/'loop.wav'
        with wave.open(str(raw),'wb') as f:
            f.setparams((1,2,rate,len(loop),'NONE','not compressed'));f.writeframes(loop.tobytes())
        work=normalize(raw,temp/'work.wav',target,1)
        music=normalize(AUDIO/'sources/lanhuacao-loop-original.wav',temp/'music.wav',target,2)
        for name,info in [('work',work),('music',music)]:
            if abs(float(info['input_i'])-target)>.3 or float(info['input_tp'])>-2.8:
                raise ValueError(f'{name}: loudness/peak check failed: {info}')
        shutil.copy2(temp/'work.wav',AUDIO/'tractor_work.wav')
        shutil.copy2(temp/'music.wav',AUDIO/'lanhuacao_loop.wav')
    results={'target_lufs':target,'true_peak_ceiling_dbtp':-3,'reference':str(REFERENCE.relative_to(ROOT)),
        'work':{'source':'assets/audio/sources/sfxmint-tractor-02.mp3','circular_overlap_seconds':.12,
                'duration':len(loop)/rate,'measured':work},
        'music':{'source':'assets/audio/sources/lanhuacao-loop-original.wav','measured':music}}
    for key,filename in [('work','tractor_work.wav'),('music','lanhuacao_loop.wav')]:
        results[key]['wav_sha256']=hashlib.sha256((AUDIO/filename).read_bytes()).hexdigest()
    (AUDIO/'loudness-calibration.json').write_text(json.dumps(results,indent=2)+'\n')
    return results


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
