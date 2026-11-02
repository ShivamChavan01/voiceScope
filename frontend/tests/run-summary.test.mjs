import assert from 'node:assert/strict';import {test} from 'node:test';import {parseRunSummary} from '../src/lib/run-summary.ts';
const empty={total_calls:0,real_calls:0,demo_calls:0,completed_calls:0,evaluated_real_calls:0,flagged_calls:0,escalated_calls:0,hallucination_rate:null,escalation_rate:null,confirmed_policy_calls:0,review_calls:0,evaluated_policy_calls:0,legacy_calls:0,scope:'all_time_persisted_runs'};
test('summary preserves empty, synthetic-only and real-only scopes without deriving false totals',()=>{
 for(const value of [empty,{...empty,total_calls:6,demo_calls:6,completed_calls:6},{...empty,total_calls:6,real_calls:6,completed_calls:6,legacy_calls:3,confirmed_policy_calls:2,evaluated_policy_calls:3}])assert.deepEqual(parseRunSummary(value),value);
});
test('malformed, partially populated or inconsistent summary responses cannot become measured zeros',()=>{
 for(const value of [null,{},[],{...empty,legacy_calls:undefined},{...empty,total_calls:6},{...empty,real_calls:-1},{...empty,legacy_calls:1},{...empty,confirmed_policy_calls:'0'},{...empty,scope:'unknown'},{...empty,hallucination_rate:NaN}])assert.throws(()=>parseRunSummary(value),/invalid response/);
});
