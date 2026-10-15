"""Report the frozen M9 analysis; no selection, new features or outcome access."""
import importlib.util
import itertools
import json
import math
import statistics as st
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def report():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    s=importlib.util.spec_from_file_location('m9_report_registration',REPO/'tools/measure_phase_state_m9.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify()
    root=m.ROOT/'validation';m.v.core.check_capture_integrity(root)
    summary=m.v.read(root/'phase_state_summary.json');assert summary['technical_qualified']
    assert summary==m.v.read(REPO/'reports/native-phase-state-m9-summary.json')
    records=m.v.read(root/'phase_state_records.json');contents=sorted({x['content_id'] for x in records})
    fig,axes=plt.subplots(2,4,figsize=(16,7.5),sharex=True,sharey=True)
    colors=['#0072B2','#D55E00']
    for ci,content in enumerate(contents):
        for j,level in enumerate(m.TARGETS):
            ax=axes[ci,j];ax.axhspan(level-.125,level+.125,color='gray',alpha=.15)
            for hi,history in enumerate(m.m.PREFIXES):
                rows=[x for x in records if x['content_id']==content and x['input_x']==level and x['prefix']==history]
                for ri,row in enumerate(rows):
                    pairs=[(x['age_ms']/1000,x['state']['current_x']) for x in row['entries'].values() if x['state']['census_passed']]
                    ax.plot([x[0] for x in pairs],[x[1] for x in pairs],color=colors[hi],alpha=.58,lw=1,label=history if ri==0 else None)
                    tag=row['first_tags_ms']['P2']
                    if tag is not None:
                        item=row['entries'][str(tag)];ax.scatter(tag/1000,item['state']['current_x'],marker='x',color=colors[hi],s=34)
            ax.axvline(16,color='black',ls=':',lw=.7);ax.axvline(24,color='black',ls='--',lw=.7)
            ax.set_title(content.replace('commons-','')+'; input '+format(.5*2**level,'.3f')+' Mbps',fontsize=10)
            ax.grid(alpha=.2)
            if ci==1:ax.set_xlabel('Common service age (s)')
            if j==0:ax.set_ylabel('log2(native BWE / 500 kbps)')
    axes[0,0].legend(fontsize=8)
    fig.suptitle('M9 fresh native contexts: four independent runs per prefix/input/content\nGray: unchanged target caliper; x: first causal P2 tag; repeated times are not new originals',fontsize=12)
    fig.tight_layout(rect=(0,0,1,.93));fig.savefig(REPO/'reports/native-phase-state-m9-trajectories.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(16,7.5),sharex=True,sharey=True)
    for ci,content in enumerate(contents):
        for j,level in enumerate(m.TARGETS):
            ax=axes[ci,j];rows=[x for x in summary['residuals'] if x['content']==content and x['input_x']==level]
            ax.axhline(0,color='black',lw=.6);ax.axhline(.25,color='gray',ls=':');ax.axhline(-.25,color='gray',ls=':')
            for method,color,offset in [('B0',colors[0],-.3),('compact',colors[1],.3)]:
                for row in rows:
                    vals=row[method+'_conditional_change_residual']['values']
                    if vals:
                        mean=st.mean(vals);ax.errorbar(row['age_ms']/1000+offset,mean,yerr=[[mean-min(vals)],[max(vals)-mean]],fmt='o',color=color,ms=3,capsize=2)
                        ax.annotate(str(len(vals)),(row['age_ms']/1000+offset,mean),xytext=(1,5),textcoords='offset points',fontsize=7,color=color)
            ax.set_title(content.replace('commons-','')+'; input '+format(.5*2**level,'.3f')+' Mbps',fontsize=10);ax.grid(alpha=.2)
            if ci==1:ax.set_xlabel('Causal matching landmark (s)')
            if j==0:ax.set_ylabel('Prefix difference in subsequent BWE change (octaves)')
    fig.suptitle('Residual prefix dependence after frozen causal matching\nBlue: BWE only; orange: compact history; ranges of paired values, numbers = matched pairs (required 4)',fontsize=12)
    fig.tight_layout(rect=(0,0,1,.93));fig.savefig(REPO/'reports/native-phase-state-m9-residuals.png',dpi=150);plt.close(fig)
    cells=[]
    for content in contents:
        for level in m.TARGETS:
            originals=[x for x in records if x['content_id']==content and x['input_x']==level]
            rrows=[x for x in summary['residuals'] if x['content']==content and x['input_x']==level]
            onsets=[x['first_future_verified_D1_ms']/1000 for x in originals if x['first_future_verified_D1_ms'] is not None]
            late=rrows[-1]
            cells.append({'content':content,'input_x':level,'originals':len(originals),'D1_future_verified_onsets':len(onsets),'onset_seconds':onsets,
                'P2_first_tags':sum(x['first_tags_ms']['P2'] is not None for x in originals),
                'P2_first_future_verified':sum(x['entries'][str(x['first_tags_ms']['P2'])]['future']['passed'] for x in originals if x['first_tags_ms']['P2'] is not None),
                'late_B0_pairs':late['B0_matching_count'],'late_compact_pairs':late['compact_matching_count'],
                'late_compact_residual_range':late['compact_conditional_change_residual'],
                'late_compact_future_w_infinity':late['compact_conditional_future_w_infinity'],
                'compact_full_coverage_landmarks':sum(x['compact_full_coverage'] for x in rrows),'registered_landmarks':len(rrows)})
    data={'abi':'native_phase_state_m9_reporting_v1','summary_sha256':m.v.sha(root/'phase_state_summary.json'),'cells':cells,
        'figures':['reports/native-phase-state-m9-trajectories.png','reports/native-phase-state-m9-residuals.png'],
        'new_state_search':False,'receiver_outcomes_read':False,'repeated_ages_are_independent':False}
    m.v.write(REPO/'reports/native-phase-state-m9-reporting.json',data)
    return {'report_cells':len(cells),'figures':len(data['figures']),'new_state_search':False}

if __name__=='__main__':print(json.dumps(report()))
