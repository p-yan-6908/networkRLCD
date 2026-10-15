"""Render frozen M8 support results and unaggregated BWE trajectories; no new rules."""
import importlib.util
import json
import math
import statistics as st
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m8_reporting_registration',REPO/'tools/measure_bwe_transients_m8.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def registered_failure_diagnostic(root):
    records=m.v.read(root/'step_response_records.json');ages={}
    for age in m.DESIGN['candidate_ages_ms']:
        key=str(age);all_counts,tag_counts=Counter(),Counter();tags=0
        for record in records:
            q=record['candidates'][key]
            all_counts.update({k:int(not value) for k,value in q['future'].get('components',{}).items()})
            if q['state']['dynamic_tag']:
                tags+=1;tag_counts.update({k:int(not value) for k,value in q['future'].get('components',{}).items()})
        ages[key]={'occurrences':64,'all_future_component_failures':dict(all_counts),'dynamic_tags':tags,
                   'future_component_failures_among_dynamic_tags':dict(tag_counts)}
    result={'abi':'native_bwe_transients_m8_registered_component_diagnostic_v1','ages':ages,
            'new_features_or_thresholds':False,'registered_labels_only':True}
    m.v.write(REPO/'reports/native-bwe-transients-m8-support-failure-diagnostic.json',result)
    return result


def report():
    m.verify();root=m.ROOT/'characterization';p,index=m.v.core.check_capture_integrity(root)
    summary=m.v.read(root/'system_id_summary.json');selection=summary['selection'];assert m.v.read(root/'mechanism_qualification_gate.json')['passed']
    registered_failure_diagnostic(root)
    contents=sorted({t['content_id'] for t in p['trials']});orders=list(m.ORDERS);paths=[]
    fig,axes=plt.subplots(2,2,figsize=(15,9),constrained_layout=True,sharex=True,sharey=True)
    for ci,content in enumerate(contents):
        for oi,order in enumerate(orders):
            ax=axes[ci,oi]
            for t in [t for t in p['trials'] if t['content_id']==content and t['input_order']==order]:
                directory=root/'sessions'/t['id'];sender=m.v.read(directory/'sender_observations.json');points=m.parent.points_for(sender)
                start=m.v.read(directory/'phase_windows.json')['phase_windows'][1]['start_ms']
                values=[q for q in points if start<=q['ms']<=start+96000 and q['valid'] and q['bwe']>0]
                color='#176da3' if t['prefix']==m.PREFIXES[0] else '#bd5b2c'
                ax.plot([(q['ms']-start)/1000 for q in values],[math.log2(q['bwe']/500000) for q in values],
                        color=color,linestyle='-' if t['repetition']==0 else '--',lw=.9,alpha=.85,
                        label=t['prefix'].replace('_prefix','')+f' r{t["repetition"]}')
            rates=m.ORDERS[order];ax.step([0,24,48,72,96],[math.log2(x/.5) for x in rates]+[math.log2(rates[-1]/.5)],where='post',color='black',lw=1.5,label='Known controlled service')
            ax.axvspan(24,96,color='grey',alpha=.06)
            for time in (24,48,72):ax.axvline(time,color='grey',lw=.6,linestyle=':')
            ax.set(title=content.split('_')[1].capitalize()+' — '+('initial low, then common H/L/H' if oi==0 else 'initial high, then common H/L/H'),xlim=(0,96))
            ax.grid(alpha=.15)
    axes[0,0].legend(fontsize=7,ncol=2)
    for ax in axes[-1,:]:ax.set_xlabel('Seconds since controlled-service phase start')
    for ax in axes[:,0]:ax.set_ylabel('log2(BWE or service / 500 kbps)')
    fig.suptitle('M8: all sixteen fresh native trajectories under fixed service\nTwo repeats per content × prefix × input-order cell; synthetic service, no action/QoE analysis',fontsize=12)
    path=REPO/'reports/native-bwe-transients-m8-trajectories.png';assert not path.exists();fig.savefig(path,dpi=170);plt.close(fig);paths.append(path)
    ages=m.DESIGN['candidate_ages_ms'];x=list(range(len(ages)))
    fig,axes=plt.subplots(1,2,figsize=(13,5),constrained_layout=True,sharey=True)
    for ax,kind in zip(axes,('baseline','dynamic'),strict=True):
        true=[selection['candidates'][str(a)]['true_'+kind+'_tags'] for a in ages]
        false=[selection['candidates'][str(a)][kind+'_false_tags'] for a in ages]
        absent=[64-t-f for t,f in zip(true,false,strict=True)]
        ax.bar(x,true,color='#408b67',label='Verified for remaining plateau')
        ax.bar(x,false,bottom=true,color='#c46443',label='Tagged but later failed')
        ax.bar(x,absent,bottom=[t+f for t,f in zip(true,false,strict=True)],color='#bfc7d0',label='No causal tag')
        ax.set(xticks=x,xticklabels=[str(a//1000) for a in ages],xlabel='Fixed candidate age (seconds)',title='B0 instantaneous BWE' if kind=='baseline' else 'D1 BWE trajectory + known service history',ylim=(0,69))
        ax.axhline(64,color='black',lw=.8,linestyle='--');ax.grid(axis='y',alpha=.15)
    axes[0].set_ylabel('64 plateau occurrences nested within sixteen native runs')
    axes[1].legend(fontsize=8,loc='upper center')
    fig.suptitle('M8 prospective settling tags — all 64 verified D1 tags required at one age\nVisits and overlapping windows are not independent samples',fontsize=11)
    path=REPO/'reports/native-bwe-transients-m8-settling.png';assert not path.exists();fig.savefig(path,dpi=170);plt.close(fig);paths.append(path)
    # Reformat registered metrics without pooling phase visits or sources.
    response_rows=[]
    for content in contents:
        for prefix in m.PREFIXES:
            for order in orders:
                row={'content':content,'prefix':prefix,'input_order':order,'independent_repetitions':2}
                for phase,direction in ((2,'fall'),(3,'rise')):
                    key='__'.join(map(str,(content,prefix,order,phase)))
                    cell=summary['responses_by_content_history_order_phase'][key]
                    row[direction]=[{'estimable':q.get('estimable',False),'reason':q.get('reason'),'departure':q.get('delay'),'t50':q.get('fraction_crossings',{}).get('0.5'),
                                     't90':q.get('fraction_crossings',{}).get('0.9'),'t10_to_t90_ms_bounds':q.get('t10_to_t90_ms_bounds'),
                                     'input_normalized_overshoot_octaves':q.get('overshoot_octaves'),
                                     'late_range_octaves':q.get('late_range_octaves'),'late_drift_octaves_per_second':q.get('late_drift_octaves_per_second')}
                                    for q in cell['per_run_response']]
                response_rows.append(row)
    tag_rows=[]
    for age in ages:
        q=selection['candidates'][str(age)]
        tag_rows.append({'age_ms':age,**{key:q[key] for key in ('baseline_tags','dynamic_tags','true_baseline_tags','true_dynamic_tags','baseline_false_tags','dynamic_false_tags')},
            'dynamic_retention_of_baseline':q['dynamic_tags']/q['baseline_tags'] if q['baseline_tags'] else None,
            'dynamic_verified_fraction_among_tags':q['true_dynamic_tags']/q['dynamic_tags'] if q['dynamic_tags'] else None})
    table={'abi':'native_bwe_transients_m8_response_tables_v1','response_rows':response_rows,'tag_rows':tag_rows,
           'history_contrasts':summary['history_contrasts'],'scope':'All per-cell repetitions retained; no population pooling or new state rules.'}
    table_path=REPO/'reports/native-bwe-transients-m8-response-tables.json';m.v.write(table_path,table)
    result={'abi':'native_bwe_transients_m8_reporting_v1','summary_sha256':m.v.sha(root/'system_id_summary.json'),
        'plots':{str(p.relative_to(REPO)):m.v.sha(p) for p in paths},'selected_age_ms':selection['selected_age_ms'],
        'response_tables_sha256':m.v.sha(table_path),'controller_fitted':False,'additional_state_rules_tested_by_reporting':False,'outcomes_read':False}
    m.v.write(REPO/'reports/native-bwe-transients-m8-reporting.json',result)
    return result


if __name__=='__main__':print(json.dumps(report()))
