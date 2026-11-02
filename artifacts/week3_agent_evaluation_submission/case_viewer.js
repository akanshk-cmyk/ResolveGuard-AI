'use strict';
fetch('Cases_40.json').then(r=>r.json()).then(rows=>{
 const select=document.getElementById('case');
 for(const row of rows){const option=document.createElement('option');option.value=row['Case ID'];option.textContent=row['Case ID']+' — '+row.Input;select.append(option);}
 function show(){const row=rows.find(r=>r['Case ID']===select.value);
 document.getElementById('expected').textContent='Expected: '+row['Expected behavior'];
 document.getElementById('before').textContent=row['Baseline output (repeat 0)'];
 document.getElementById('after').textContent=row['Improved output (repeat 0)'];
 document.getElementById('before-status').textContent=row['Baseline PASS/FAIL']+'; '+JSON.stringify(row['Baseline failure category']);
 document.getElementById('after-status').textContent=row['Improved PASS/FAIL']+'; '+JSON.stringify(row['Remaining failure category']);}
 select.value='RG-033';select.addEventListener('change',show);show();
});
