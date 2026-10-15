"""Verified 60-second derivatives of retained CC BY originals; no downloads."""
import importlib.util
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location('m7_asset_dependencies', REPO / 'tools/design_native_v13.py')
v = importlib.util.module_from_spec(s)
s.loader.exec_module(v)
MANIFEST = REPO / 'data/native-m7/sources.json'


def prepare():
    assert not MANIFEST.exists(), 'preserve completed assets'
    assets = v.verify_assets()
    out = v.CACHE / 'native-state-conditioning-m7-assets'
    out.mkdir(exist_ok=False)
    contents = []
    for old in assets['content_sources']:
        c = dict(old)
        original = v.CACHE / c['original_cache_path']
        assert v.sha(original) == c['original_sha256']
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(original)], text=True))
        assert float(probe['format']['duration']) >= 60
        clip = out / (c['content_id'] + '-60s.mp4')
        command = ['ffmpeg', '-n', '-v', 'error', '-i', str(original), '-ss', '0', '-t', '60', '-an',
                   '-vf', 'fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=black',
                   '-c:v', 'libx264', '-threads', '2', '-preset', 'medium', '-crf', '18', '-profile:v', 'main', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(clip)]
        subprocess.run(command, check=True)
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,nb_frames', '-of', 'json', str(clip)], text=True))
        assert float(probe['format']['duration']) == 60 and probe['streams'][0]['nb_frames'] == '1800'
        c.update(clip_cache_path=str(clip.relative_to(v.CACHE)), clip_sha256=v.sha(clip), clip_bytes=clip.stat().st_size,
                 segment_ms=[0, 60000], looped=False, derivation='first 60 seconds; no audio; 640x360 scale/pad; 30fps; libx264 Main/yuv420p CRF18 medium; faststart',
                 source_role='Reused licensed production, new longer derivative; not an independently sourced content replication',
                 prior_45s_clip_sha256=old['clip_sha256'], derivation_command=command, derived_probe=probe)
        # The old visual review covers the old derivative; do not transfer its qualification.
        c['prior_45s_visual_review'] = c.pop('visual_review')
        contents.append(c)
    result = {'abi':'native_state_conditioning_m7_sources_v1', 'parent_manifest_sha256':v.sha(REPO/'data/native-v13/sources.json'),
              'content_sources':contents, 'network_profiles':assets['network_profiles'],
              'network_families':assets['network_families'], 'network_sources':assets['network_sources'],
              'independence':'Fresh native runs only. Reused licensed content and two trace bundles within one Mahimahi measurement program; profiles may overlap. No broad network claim.',
              'input_separation':'Constructed equal-integral early permutations; synthetic controlled conditioning; original unscaled measured-source common probe. Never pool these as wholly measured service.'}
    v.write(MANIFEST, result)
    return {'assets_verified':True, 'new_clips':len(contents), 'originals_preserved':True}


if __name__ == '__main__':
    print(json.dumps(prepare()))
