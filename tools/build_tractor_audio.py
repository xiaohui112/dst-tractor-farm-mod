#!/usr/bin/env python3
"""Synthesize original looping tractor effects and compile a real FMOD bank."""
import argparse
from array import array
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import tempfile
import uuid
import wave
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PROJECT='aom_tractor_sfx'


def guid(key):return '{'+str(uuid.uuid5(uuid.NAMESPACE_URL,PROJECT+'/'+key))+'}'


def synthesize():
    rate=44100;seconds=4;n=rate*seconds
    for name,hz in [('idle',23),('drive',37),('work',73)]:
        rng=random.Random(700+hz);pcm=array('h');filtered=0.
        for i in range(n):
            t=i/rate;angle=2*math.pi*hz*t
            # Rounded diesel exhaust pulses, low harmonics, metal rattle and air.
            pulse=(.5+.5*math.cos(angle))**7-.21
            harmonics=sum(math.sin(angle*k)/k**1.4 for k in range(1,9))
            filtered=.92*filtered+.08*(rng.random()*2-1)
            noise=filtered*(.2+.8*abs(math.sin(angle/2)))
            value=.24*pulse+.12*harmonics+.11*noise
            if name=='work':value+=.07*math.sin(2*math.pi*293*t)*(.5+.5*math.sin(2*math.pi*11*t))
            # Tiny boundary fade avoids PCM discontinuity without audible pauses.
            value*=min(1,i/(rate*.008),(n-1-i)/(rate*.008))
            pcm.append(round(max(-.95,min(.95,value))*32767))
        path=ROOT/'assets/audio'/('tractor_'+name+'.wav')
        with wave.open(str(path),'wb') as f:
            f.setparams((1,2,rate,n,'NONE','not compressed'));f.writeframes(pcm.tobytes())


def project():
    template=ET.parse(ROOT/'assets/audio/fmod/aom_irrigator_music.fdp').getroot()
    template.find('name').text=PROJECT
    template.find('currentbank').text=PROJECT
    template.find('eventcategory/name').text='set_sfx'
    defs=template.find('sounddeffolder');base_def=copy.deepcopy(defs.find('sounddef'));defs.remove(defs.find('sounddef'))
    group=template.find('eventgroup');group.find('name').text='tractor';group.find('event_nextid').text='3'
    base_event=copy.deepcopy(group.find('event'));group.remove(group.find('event'))
    bank=template.find('soundbank');bank.find('name').text=PROJECT
    base_wave=copy.deepcopy(bank.find('waveform'));bank.remove(bank.find('waveform'))
    for name in ['idle','drive','work']:
        filename='../tractor_'+name+'.wav'
        d=copy.deepcopy(base_def);d.find('name').text=name
        d.find('waveform/filename').text=filename;d.find('waveform/soundbankname').text=PROJECT;defs.append(d)
        event=copy.deepcopy(base_event);event.find('name').text=name
        event.find('layer/sound/name').text=name;event.find('mode').text='x_3d'
        event.find('headrelative').text='World_relative';event.find('category').text='set_sfx'
        event.find('mindistance').text='2';event.find('maxdistance').text='22'
        event.find('fadein_time').text='.08';event.find('fadeout_time').text='.12';group.append(event)
        wav=copy.deepcopy(base_wave);wav.find('filename').text=filename;bank.append(wav)
    for i,e in enumerate(template.iter('guid')):e.text=guid(str(i))
    out=ROOT/'assets/audio/fmod'/('aom_tractor_sfx.fdp');ET.indent(template)
    ET.ElementTree(template).write(out,encoding='utf-8',xml_declaration=True)
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--designer',type=Path,required=True);parser.add_argument('--wine',type=Path)
    args=parser.parse_args();synthesize();path=project()
    def native(p):return 'Z:'+str(p.resolve()).replace('/','\\') if args.wine else str(p.resolve())
    with tempfile.TemporaryDirectory(prefix='aom-sfx-') as folder:
        cmd=([str(args.wine)] if args.wine else [])+[str(args.designer),'-pc','-b',native(Path(folder)),native(path)]
        result=subprocess.run(cmd,cwd=path.parent,text=True,capture_output=True,errors='replace')
        print(result.stdout)
        if result.returncode:raise RuntimeError(result.stderr)
        records={}
        for ext in ['fev','fsb']:
            raw=(Path(folder)/(PROJECT+'.'+ext)).read_bytes()
            if len(raw)<128 or (ext=='fev' and raw[:4]!=b'RIFF') or (ext=='fsb' and raw[:4] not in (b'FSB4',b'FSB5')):
                raise ValueError('Invalid compiled audio bank')
            (ROOT/'mod/Tractor/sound'/(PROJECT+'.'+ext)).write_bytes(raw)
            records[ext]=hashlib.sha256(raw).hexdigest()
        (path.parent/'tractor-build.json').write_text(json.dumps({'project':PROJECT,
            'source':'Procedural original synthesis; no sampled third-party audio',
            'events':['tractor/'+n for n in ['idle','drive','work']],
            'loop_seconds':4,'sample_rate':44100,'channels':1,'sha256':records,
            'compiler_sha256':hashlib.sha256(args.designer.read_bytes()).hexdigest()},indent=2)+'\n')


if __name__=='__main__':main()
