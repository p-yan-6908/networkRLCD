"""Derive verified 130s clips from retained licensed originals; no downloads."""
import importlib.util
import json
import subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m8_asset_dependencies',REPO/'tools/design_native_v13.py')
v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
MANIFEST=REPO/'data/native-m8/sources.json'


def prepare():
    assert not MANIFEST.exists(), 'preserve existing M8 sources'
    assets=v.verify_assets();out=v.CACHE/'native-bwe-transients-m8-assets';out.mkdir(exist_ok=False)
    contents=[]
    for old in assets['content_sources']:
        c=dict(old);original=v.CACHE/c['original_cache_path'];assert v.sha(original)==c['original_sha256']
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(original)],text=True))
        assert float(probe['format']['duration'])>=130
        clip=out/(c['content_id']+'-130s.mp4')
        cmd=['ffmpeg','-n','-v','error','-i',str(original),'-ss','0','-t','130','-an','-vf',
             'fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black',
             '-c:v','libx264','-threads','2','-preset','medium','-crf','18','-profile:v','main','-pix_fmt','yuv420p','-movflags','+faststart',str(clip)]
        subprocess.run(cmd,check=True)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=width,height,nb_frames','-of','json',str(clip)],text=True))
        assert float(probe['format']['duration'])==130 and probe['streams'][0]['nb_frames']=='3900'
        c['prior_45s_visual_review']=c.pop('visual_review')
        c.update(clip_cache_path=str(clip.relative_to(v.CACHE)),clip_sha256=v.sha(clip),clip_bytes=clip.stat().st_size,
                 segment_ms=[0,130000],looped=False,derivation='first 130 seconds; no audio; 640x360 scale/pad; 30fps; x264 Main CRF18 medium; no looping',
                 derivation_command=cmd,derived_probe=probe,source_role='Reused licensed production; new longer derivative, not new independent content')
        contents.append(c)
    result={'abi':'native_bwe_transients_m8_sources_v1','parent_manifest_sha256':v.sha(REPO/'data/native-v13/sources.json'),
            'content_sources':contents,**{k:assets[k] for k in ('network_sources','network_profiles','network_families')},
            'independence':'Fresh native contexts only; reused two productions and measured-source dependencies. Controlled plateaus are synthetic service, not measured-network replication.',
            'input_separation':'Constructed equal-multiset measured-source prefix; synthetic fixed service steps; original unscaled measured-source probe.'}
    v.write(MANIFEST,result)
    return {'clips_verified':2,'duration_seconds':130,'originals_and_old_clips_preserved':True}


if __name__=='__main__':print(json.dumps(prepare()))
