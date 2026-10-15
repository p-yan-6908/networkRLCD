"""Report M7RA registered gates and BWE/service trajectories; no new states or fits."""
import importlib.util
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m7_reporting_registration',REPO/'tools/measure_state_conditioning_m7ra.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def report():
    m.verify()
    feasibility=m.v.read(m.ROOT/'feasibility/mechanism_qualification_gate.json')
    validation_path=m.ROOT/'validation/mechanism_qualification_gate.json'
    assert feasibility['passed'] or not (m.ROOT/'validation/sessions').exists()
    stages={'feasibility':feasibility}
    if validation_path.exists():stages['validation']=m.v.read(validation_path)
    output={'abi':'native_state_conditioning_m7ra_summary_v1','registration_commit':'c992058a9d8c0569c5544aea1d22507ca1b7b4f0',
            'design_sha256':m.v.sha(m.CONFIG),'stages':{},'native_common_support_established':False,
            'validation_started':(m.ROOT/'validation/sessions').exists(),'untouched_validation_originals':0 if validation_path.exists() else 128,
            'delivery_qoe_action_outcomes_read':False,'additional_state_representations_tested_on_m6r':False,
            'predictors_fitted':False,'controller_fitted':False,'v13_action_stage_reopened':False,
            'future_action_stage_enabled':False,'population_equivalence_established':False}
    for stage,gate in stages.items():
        m.v.core.check_capture_integrity(m.ROOT/stage)
        rows=gate['sessions']
        output['stages'][stage]={'gate_sha256':m.v.sha(m.ROOT/stage/'mechanism_qualification_gate.json'),
            'originals':len(rows),'technical_qualified':sum(r['technical_passed'] for r in rows),
            'baseline_members':sum(r.get('baseline_member',False) and r['technical_passed'] for r in rows),
            'history_members':sum(r.get('history_member',False) and r['technical_passed'] for r in rows),
            'state_membership_passed':gate['state_membership_passed'],'repeatability_passed':gate['repeatability_passed'],
            'all_pair_probe_fidelity_passed':all(x['passed'] for x in gate['pair_fidelity'].values()),'passed':gate['passed'],
            'groups':gate['groups'],'panel_gates':gate['panel_gates'],'common_overlap_octaves':gate['common_overlap_octaves'],
            'per_original':[{k:r.get(k) for k in ['trial','prefix','content_id','network_family','target_x','technical_passed','reason',
                                                'baseline_member','history_member','entry','probe_windows','conditioning']} for r in rows]}
        clocks=[r['clock'] for r in rows if 'clock' in r]
        cond=[r['conditioning'] for r in rows if 'conditioning' in r]
        output['stages'][stage]['instrumentation']={
            'full_clock_max_heldout_width_ms':max((c['full'].get('max_held_out_width_ms',0) for c in clocks),default=None),
            'beginning_clock_max_heldout_width_ms':max((c['beginning'].get('max_held_out_width_ms',0) for c in clocks),default=None),
            'maximum_readback_delay_ms':max((c['maximum_ack_ms'] for c in cond),default=None),
            'maximum_conditioning_command_lateness_ms':max((c['maximum_lateness_ms'] for c in cond),default=None),
            'maximum_source_tick_error_ms':max((r['fidelity']['maximum_tick_error_ms'] for r in rows if 'fidelity' in r),default=None),
            'maximum_startup_poll_gap_ms':max((r['startup']['maximum_poll_gap_ms'] for r in rows if 'startup' in r),default=None)}
    output['native_common_support_established']=stages.get('validation',{}).get('native_common_support_established',False)
    if not feasibility['passed']:
        output['result']='instrumentation-limited feasibility failure' if not feasibility['technical_passed'] else 'fixed-recipe state-creation feasibility failure'
    else:
        output['result']='prospective common support qualified' if output['native_common_support_established'] else 'validation support failure'
    plots=[]
    if all((m.ROOT/'feasibility/sessions'/r['trial']/'sender_observations.json').exists() for r in feasibility['sessions']):
        fig,axes=plt.subplots(2,1,figsize=(12,8),constrained_layout=True,sharex=True)
        for ax,target in zip(axes,(0.,1.5),strict=True):
            ax.axhspan(target-.125,target+.125,color='#4a9668',alpha=.17,label='Frozen target ±0.125 octave')
            ax.axvspan(27,32,color='#9fa7b4',alpha=.15,label='Feedback off; service held')
            ax.axvline(32,color='black',lw=.8,linestyle=':',label='Common measured-source probe')
            for prefix,color in zip(m.PREFIXES,('#176da3','#bd5b2c'),strict=True):
                row=next(r for r in feasibility['sessions'] if r['target_x']==target and r['prefix']==prefix)
                directory=m.ROOT/'feasibility/sessions'/row['trial']
                sender=m.v.read(directory/'sender_observations.json');points=m.points_for(sender)
                phase=m.v.read(directory/'phase_windows.json')['phase_windows'][1]['start_ms']
                valid=[p for p in points if p['valid'] and p['bwe']>0]
                ax.plot([(p['ms']-phase)/1000 for p in valid],[math.log2(p['bwe']/500000) for p in valid],color=color,lw=1.2,label=prefix.replace('_prefix','')+' BWE')
                commands=m.v.read(directory/'conditioning_evidence.json')['commands']
                ax.step([0]+[(c['browser_receive_ms']-phase)/1000 for c in commands]+[32],
                        [target]+[math.log2(c['readback']['capacity_mbps']/.5) for c in commands]+[math.log2(commands[-1]['readback']['capacity_mbps']/.5)],
                        where='post',color=color,alpha=.55,lw=.9,linestyle='--',label=prefix.replace('_prefix','')+' controlled service')
                if row.get('entry',{}).get('passed'):
                    ax.scatter([(row['entry']['cutoff_ms']-phase)/1000],[row['entry']['x']],color=color,s=45,zorder=5)
            ax.set(ylabel='log2(rate / 500 kbps)',title=f'Target {500*2**target:.0f} kbps; fixed recipe, no repeated-run population claim',xlim=(-10,45))
            ax.grid(alpha=.15)
        axes[0].legend(fontsize=7,ncol=2,loc='upper right')
        axes[-1].set_xlabel('Seconds relative to conditioning start; prior-history prefix is −10…0')
        fig.suptitle('M7RA feasibility: native BWE and controlled service only\nFour original sessions; all prior freezes retained',fontsize=12)
        path=REPO/'reports/native-state-conditioning-m7ra-trajectories.png'
        assert not path.exists();fig.savefig(path,dpi=170);plt.close(fig);plots.append(str(path.relative_to(REPO)))
    output['plots']={name:m.v.sha(REPO/name) for name in plots}
    m.v.write(m.ROOT/'feasibility/state_creation_summary.json',output)
    m.v.write(REPO/'reports/native-state-conditioning-m7ra-summary.json',output)
    return {k:output[k] for k in ('result','native_common_support_established','validation_started','untouched_validation_originals','stages')}


if __name__=='__main__':
    result=report()
    print(json.dumps({k:v for k,v in result.items() if k!='stages'}))
