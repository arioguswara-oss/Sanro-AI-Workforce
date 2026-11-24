import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {WorkforceMonitor} from '../dist-monitor/workforce-monitor.js';

test('compiled monitoring component renders status and escapes values without mutation controls',()=>{
  const snapshot={schema_version:1,read_only:true,project_id:'<script>unsafe</script>',hermes_health:{status:'UNAVAILABLE'},queue:{queued:0,running:0},workers:[{worker_id:'developer',role:'developer',status:'unknown',data_state:'STALE',job_id:null,last_heartbeat:null}],runs:[],approval:{pending_count:0,live_native_status:'UNAVAILABLE'},reports:{queued:0,acknowledged:0},models:[],draft_pr:null};
  const html=renderToStaticMarkup(React.createElement(WorkforceMonitor,{snapshot}));
  assert.match(html,/STALE/);assert.match(html,/UNAVAILABLE/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script|<button|<form|<input|<textarea/);
  assert.match(renderToStaticMarkup(React.createElement(WorkforceMonitor)),/belum tersedia/);
});
