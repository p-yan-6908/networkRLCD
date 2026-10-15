"""Editorial/plots for frozen M10 estimates, without fitting or new features."""
from __future__ import annotations
import importlib.util
import json
import statistics as st
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('m10_reporting',REPO/'tools/measure_mechanism_observability_m10.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=m.v

def label(content):return 'Kampar' if 'kampar' in content else 'Volga'
def span(values):
    q=[x for x in values if x is not None]
    return f'{min(q):+.3f}..{max(q):+.3f}' if q else 'unavailable'

def report():
    m.verify();opened=[stage for stage in ('instrumentation','development') if (m.ROOT/stage/'mechanism_qualification_gate.json').exists()]
    gates={stage:v.read(m.ROOT/stage/'mechanism_qualification_gate.json') for stage in opened}
    lines=['# M10: fresh causal mechanism observability assay','',
        'Scientific registration: `03aac061347fb9c9c44b69a8f8f900e27720c60e`. This report uses fresh M10 support data only. '
        'M9R and prior freezes remain closed to new state searches. Receiver outcomes remain unopened.','',
        '## Acquisition and causal observability','',
        '| Stage | Planned | Qualified | All mandatory gates |','|---|---:|---:|---|']
    for stage,g in gates.items():lines.append(f'|{stage}|{g["planned_sessions"]}|{g["qualified_sessions"]}|{g["passed"]}|')
    lines+=['','Every accepted online mechanism value is tied to its actual sender receipt. Relay snapshots are pure reads, '
        'acknowledged before use. Full/beginning fitted clocks are used only for offline acquisition checks; '
        'native timestamps remain unmapped. RTCP RTT and ICE RTT remain separate. Observed report/RTT-counter advance '
        'age is a detection-age bound, not native transport-CC feedback-generation age.','',
        'Optional channel qualification in every original:','',
        '| Stage | RTCP RTT | Observed counter age |','|---|---|---|']
    for stage,g in gates.items():
        q=g['optional_channels_qualified_every_original'];lines.append(f'|{stage}|{q["rtcp_rtt"]}|{q["observed_feedback_counter_age"]}|')
    root=m.ROOT/opened[-1];science=root/'mechanism_analysis.json'
    result={'abi':'native_mechanism_observability_m10_reporting_v1','gates':{k:{q:g[q] for q in ('passed','planned_sessions','qualified_sessions','optional_channels_qualified_every_original')} for k,g in gates.items()},
        'receiver_outcomes_read':False,'actions':False,'controller_fitted':False,'common_support_established':False}
    if not all(g['passed'] for g in gates.values()) or not science.exists():
        lines+=['','## Decision','','Instrumentation-limited stop. No development mechanism or future-state interpretation. '
            'Preserve every failed original and unavailable counter. Do not relax gates or fit a predictor.']
        result['classification']='instrumentation-limited; no mechanism/state interpretation'
    else:
        x=v.read(science);pairs=x['pair_records'];records=v.read(root/'mechanism_records.json')
        lines+=['','## Stationary state and moving trajectories','','The eight development originals provide two repeats/history '
            'at one input. They cannot meet the unchanged four-member, range/SD/overlap confirmation requirements. '
            'These requirements have not been waived.','',
            '| Rule | First tags /8 | Future-verified first tags | Nested tags | Verified nested tags |',
            '|---|---:|---:|---:|---:|']
        for k,z in x['methods'].items():lines.append(f'|{k}|{z["first_tags"]}|{z["first_future_verified"]}|{z["nested_tags"]}|{z["nested_future_verified_tags"]}|')
        lines+=['',f'There were **{x["positive_future_stationarity_labels_nested"]}/{x["total_nested_queries"]}** positive future-stationarity labels '
            '(nested observations in eight originals). No classifier or regressor was fitted. '
            'P2 precision is unestimable if it emits no tags.','',
            f'Of {len(pairs)} nested pair/landmark contrasts, **{x["compact_matched_pairs_nested"]}** met the unchanged compact sender matching rule; '
            f'**{x["compact_matched_future_divergent_pairs_nested"]}** exceeded the future-distribution 0.25-octave bound. '
            f'**{x["compact_matched_moving_repeatable_pairs_nested"]}** remained within that bound. '
            'Moving marginal repeatability does not establish stationary state, a predictable trajectory, or common causal action support.','',
            '### Every prepaired cross-history landmark','',
            '| Content | Age s | Compact matched /2 | Future divergent among matched | Future W-infinity range | Subsequent-change residual range |',
            '|---|---:|---:|---:|---|---|']
        for content in sorted({r['content_id'] for r in records}):
            for age in m.DESIGN['landmarks_ms']:
                rows=[r for r in pairs if r['content']==content and r['age_ms']==age and r['pair_type']=='prepaired_cross_history']
                lines.append(f'|{label(content)}|{age/1000:g}|{sum(r["compact_matched"] for r in rows)}|'
                    f'{sum(r["compact_matched"] and r["future_divergent"] for r in rows)}|'
                    f'{span([r["future_w_infinity_octaves"] for r in rows])}|{span([r["future_change_residual_octaves"] for r in rows])}|')
        lines+=['','## Predeclared mechanism contrasts','','The resolution flags below are descriptive contrasts, '
            'not learned features or new eligibility gates. Counts share originals, pairs and ages; they are not independent evidence. '
            'Selected-context differences do not identify causal mediation. Every raw signed contrast, including within-history '
            'and crossed-repeat controls, is retained in the summary JSON.','',
            '| Channel | Compact divergent: available /total | Contrast flags | Compact nondivergent: available /total | Contrast flags | Replicated content/landmark contrasts with controls |',
            '|---|---:|---:|---:|---:|---:|']
        for key in m.DESIGN['contrast_resolution']:
            name=key.removesuffix('_octaves');ds=[r for r in pairs if r['compact_matched'] and r['future_divergent']];cs=[r for r in pairs if r['compact_matched'] and r['future_divergent'] is False]
            values=[[r['mechanism_contrasts'][name] for r in rows] for rows in (ds,cs)]
            flags=[sum(q['resolution_flag'] is True for q in vals) for vals in values];available=[sum(q['available'] for q in vals) for vals in values]
            replicated=sum(r['channel']==name and r['criterion_met'] for r in x['repeatability_audit'])
            lines.append(f'|{name}|{available[0]}/{len(ds)}|{flags[0]}|{available[1]}/{len(cs)}|{flags[1]}|{replicated}|')
        lines+=['','RTCP generation age, transport-CC feedback age and internal browser/pacer/cwnd state are not exposed. '
            'The owned relay is only one queue in the TURN/TCP path; a small or empty owned queue does not establish an empty end-to-end path. '
            'Constant cap readback cannot discriminate contexts; encoder/send counters can vary with the estimator and content. '
            'Concurrent measured contrasts can be consequences of BWE or common causes, so this assay cannot establish causal explanations.','',
            '## Scientific decision','']
        motivated=x['trajectory_followup_motivation_channels']
        if motivated:
            lines+=['The frozen descriptive motivation criterion was met by: **'+', '.join(motivated)+'**. '
                'This justifies considering a separately preregistered trajectory-state development question, '
                'with new untouched confirmation. It does not establish a state or permit actions.']
        else:
            lines+=['No channel met the frozen requirement for a repeated same-direction contrast with suitable controls '
                'in both contents. The assay does not establish an observable mechanism explanation or prospectively '
                'identifiable trajectory state. A trajectory-state efficacy study is not yet justified by this assay.']
        lines+=['','A new study would need a fresh preregistration and new captures, explicit causal availability, '
            'adequate repeated controls, and an independent demonstration of its proposed trajectory contract. '
            'The existing stationary/common-support gates remain binding for their stated target. No longer fixed wait, '
            'additional search of M9R, opened successor allocation, stability fit, action-value estimate or controller.','',
            '## Limits','','Two reused content productions; one synthetic controlled input and one measurement program; '
            'only two development repeats/history. No new independent network family, population effect or broad replication claim.']
        result.update(classification='qualified fresh development mechanism assay',positive_future_stationarity_labels_nested=x['positive_future_stationarity_labels_nested'],
            compact_matched_pairs_nested=x['compact_matched_pairs_nested'],compact_divergent_pairs_nested=x['compact_matched_future_divergent_pairs_nested'],
            trajectory_followup_motivation_channels=motivated,analysis_sha256=v.sha(science),no_predictor_fitted=True)
        plot(root,records)
    lines+=['','## Preservation','','All prior freezes and old untouched allocations are preserved; licensed originals '
        'and derivatives remain external. Complete new raw evidence, field missingness, source snapshots and gate failures '
        'are retained. The new private receipt pins the immutable archive revision and fresh object/member checksum verification.']
    text='\n'.join(lines)+'\n';(REPO/'docs/NATIVE_MECHANISM_OBSERVABILITY_M10_RESULTS.md').write_text(text)
    v.write(REPO/'reports/native-mechanism-observability-m10-reporting.json',result)
    return result

def plot(root,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,8),sharex=True)
    contents=sorted({r['content_id'] for r in records})
    colors={m.parent.m.PREFIXES[0]:'#2563eb',m.parent.m.PREFIXES[1]:'#d94801'}
    for col,content in enumerate(contents):
        for record in [r for r in records if r['content_id']==content]:
            d=root/'sessions'/record['id'];common=v.read(d/'phase_windows.json')['phase_windows'][1]['start_ms']+24000
            sender=v.read(d/'sender_observations.json');points=m.parent.m.parent.points_for(sender)
            q=[n for n in points if common<=n['ms']<=common+63800]
            kwargs={'color':colors[record['prefix']],'linestyle':'-' if record['repetition']==0 else '--','linewidth':.8,'alpha':.85}
            axes[0,col].plot([(n['ms']-common)/1000 for n in q],[n['bwe']/1000000 for n in q],label=f'{record["prefix"]}, r{record["repetition"]+1}',**kwargs)
            rs=v.read(d/'mechanism_relay_browser.json')['records'];rs=[n for n in rs if common<=n['browser_receive_ms']<=common+63800]
            axes[1,col].plot([(n['browser_receive_ms']-common)/1000 for n in rs],
                [n['snapshot']['a_to_b']['queued_wire_bytes']/(n['snapshot']['capacity_mbps']*125) for n in rs],**kwargs)
            ns=v.read(d/'mechanism_native.json')['records'];ns=[n for n in ns if common<=n['available_ms']<=common+63800 and n['rtcp']['roundTripTime']['status']=='present']
            axes[2,col].plot([(n['available_ms']-common)/1000 for n in ns],[n['rtcp']['roundTripTime']['value']*1000 for n in ns],**kwargs)
        axes[0,col].axhline(m.DESIGN['service_mbps'][1],color='black',ls=':',lw=.8,label='controlled service')
        axes[0,col].set_title(label(content));axes[2,col].set_xlabel('Seconds after scheduled common-service change')
        axes[0,col].legend(fontsize=7,loc='upper left')
        for row in range(3):axes[row,col].grid(alpha=.2)
    for row,title in enumerate(['Native BWE (Mbps)','Owned forward queue (service ms)','Native RTCP RTT (ms)']):axes[row,0].set_ylabel(title)
    fig.suptitle('M10 fresh development: moving BWE and observed mechanisms\nTwo histories × two repeats per content; no receiver outcome analysis')
    fig.tight_layout();fig.savefig(REPO/'reports/native-mechanism-observability-m10-trajectories.png',dpi=160);plt.close(fig)

if __name__=='__main__':print(json.dumps(report()))
