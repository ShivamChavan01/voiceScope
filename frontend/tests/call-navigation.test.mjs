import assert from 'node:assert/strict';
import {test} from 'node:test';
import {callNavigationUrl,syntheticScenarioNote} from '../src/lib/call-navigation.ts';
test('opening and closing call URLs preserve unrelated query and hash, including invalid identifiers',()=>{
 const current='https://demo.example/runs?qa=keep&call=missing#evidence';
 assert.equal(callNavigationUrl(current,null),'/runs?qa=keep#evidence');
 const next=callNavigationUrl(current,'a/b ?&雪');const url=new URL(next,'https://demo.example');assert.equal(url.searchParams.get('call'),'a/b ?&雪');assert.equal(url.searchParams.get('qa'),'keep');assert.equal(url.hash,'#evidence');
 assert.equal(callNavigationUrl('https://demo.example/runs',null),'/runs');
});
test('earlier duplicate samples are described rather than deleted or relabeled as real',()=>{
 assert.match(syntheticScenarioNote('demo-review-promise'),/same authored conversation as demo-staging-policy/);
 assert.equal(syntheticScenarioNote('real-user-call'),null);assert.equal(syntheticScenarioNote('constructor'),null);assert.equal(syntheticScenarioNote(''),null);assert.equal(syntheticScenarioNote('demo-staging-stt'),null);
});
