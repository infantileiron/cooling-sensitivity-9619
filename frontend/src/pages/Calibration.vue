<script setup lang="ts">
import {ref,computed,watch,onMounted} from 'vue';
import {calibrations} from '../stores/calibrations';
import * as calibrationApi from '../api/calibrations';
import {models} from '../stores/models';
import {spaces} from '../stores/spaces';
import {studies} from '../stores/studies';
import {canWrite} from '../stores/auth';
import {useTask} from '../hooks/useTask';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import StatusPill from '../components/common/StatusPill.vue';
import EmptyState from '../components/common/EmptyState.vue';
import {fixed,scientific} from '../utils/format';

const name=ref('');
const description=ref('实测冷却观测加权校准；重复工况按权重合并，LOCO整列剔除工况。');
const modelId=ref('demo-model');
const observations=ref('condition_id,flow,inlet,load,fan,approach,eff,response,weight\nc1,25.034,30.793,0.553,38.966,7.483,82.931,1653.717,1.120\nc2,30.000,28.310,0.536,47.241,4.724,67.069,1558.147,1.520\nc3,26.690,28.862,0.847,35.517,5.414,72.586,1782.533,1.210\nc4,20.069,30.241,0.519,34.828,3.172,71.897,1341.793,0.890\nc5,29.172,28.034,0.640,41.724,3.000,67.759,1521.282,1.470\nc5,29.172,28.034,0.640,41.724,3.000,67.759,1521.284,1.050\nc6,22.138,32.448,0.743,33.448,4.207,77.414,1647.711,1.700\nc7,25.448,26.655,0.502,46.552,7.138,65.000,1568.247,1.320\nc8,22.552,27.207,0.605,43.103,5.586,73.966,1531.239,1.190\nc9,27.517,27.483,0.657,39.655,5.931,69.138,1636.803,0.830\nc10,21.724,26.103,0.916,34.138,5.241,78.103,1705.803,1.590\nc11,18.000,26.379,0.829,49.310,6.966,82.241,1784.057,1.130\nc12,22.966,29.414,0.674,45.862,7.655,76.034,1778.836,1.540\nc12,22.966,29.414,0.674,45.862,7.655,76.034,1780.037,0.810\nc13,23.793,25.276,0.864,32.069,6.448,81.552,1693.542,0.860\nc14,29.586,29.138,0.691,44.483,6.103,65.690,1779.140,1.230\nc15,25.862,26.931,0.898,37.586,3.862,85.000,1688.344,0.850\nc16,27.103,30.517,0.709,42.414,4.552,74.655,1691.922,1.020\nc17,24.207,33.000,0.881,47.931,8.000,73.276,2130.113,1.440\nc18,18.414,31.897,0.795,40.345,3.690,80.172,1664.152,1.160\nc19,19.655,31.069,0.812,41.034,4.379,66.379,1740.629,1.010\nc20,21.310,25.000,0.622,45.172,7.310,79.483,1571.769,1.380\nc21,20.483,31.621,0.467,31.379,5.069,80.862,1392.467,1.530\nc22,27.931,29.690,0.933,30.690,3.345,68.448,1770.467,1.650\nc23,26.276,25.828,0.950,30.000,6.276,76.724,1798.627,1.240\nc23,26.276,25.828,0.950,30.000,6.276,76.724,1798.712,1.720\nc24,24.621,29.966,0.484,36.207,6.621,83.621,1501.686,1.010\nc25,28.345,27.759,0.760,50.000,4.034,70.517,1723.290,1.180\nc26,19.241,31.345,0.726,48.621,4.897,75.345,1721.409,1.740\nc27,20.897,28.586,0.571,43.793,7.828,71.207,1649.455,1.360\nc28,28.759,32.724,0.588,36.897,6.793,84.310,1715.462,0.950\nc29,18.828,32.172,0.450,38.276,5.759,69.828,1478.073,1.800\nc30,23.379,25.552,0.778,32.759,3.517,78.793,1485.335,1.290');
const selected=ref('');
const {error,busy,act}=useTask();

const studyName=ref('');
const spaceName=ref('');
const sourceSpaceId=ref('');
const trajectories=ref(24),levels=ref(6),power=ref(12),seed=ref(20261112);
const studyError=ref(''),studyBusy=ref(false);

onMounted(()=>Promise.all([calibrations.load(),models.load(),spaces.load(),studies.load()]));

const current=computed(()=>calibrations.items.value.find((r:any)=>r.id===selected.value)||calibrations.items.value[0]);
const sourceModel=computed(()=>models.items.value.find((m:any)=>m.id===modelId.value));
const factorIds=computed(()=>(sourceModel.value?.factors||[]).map((f:any)=>f.factor_id));
// the study form belongs to the selected calibration's source model, not the
// model currently chosen in the import form
const studySourceModelId=computed(()=>current.value?.model_id||modelId.value);
const modelSpaces=computed(()=>spaces.items.value.filter((s:any)=>s.model_id===studySourceModelId.value));
watch(modelSpaces,(list)=>{if(!list.some((s:any)=>s.id===sourceSpaceId.value))sourceSpaceId.value=list[0]?.id||''},{immediate:true});

function submit(){
 act(async()=>{
  const r=await calibrations.create({name:name.value,description:description.value,model_id:modelId.value,observations_csv:observations.value});
  selected.value=r.id;name.value='';
 });
}
async function buildStudy(){
 if(!current.value)return;
 studyError.value='';studyBusy.value=true;
 try{
  const study=await calibrationApi.createStudy(current.value.id,{
   study_name:studyName.value,source_space_id:sourceSpaceId.value,space_name:spaceName.value,
   trajectories:trajectories.value,levels:levels.value,power:power.value,seed:seed.value});
  await Promise.all([studies.load(),spaces.load()]);
  studyName.value='';spaceName.value='';
  return study;
 }catch(e){studyError.value=(e as Error).message}finally{studyBusy.value=false}
}
const num=(v:unknown,n=4)=>v===null||v===undefined?'—':fixed(v,n);
</script>

<template>
 <PageHeading index="06 / 代理校准" title="用实测冷却数据，重新拟合受控代理。" note="按工况加权合并重复观测，拟合截距、各因子一次/二次项与已有交互项。SVD加权最小二乘配合列缩放，因子跨度悬殊仍稳定；秩不足或非正权重整批拒绝，不产生新版代理。"/>
 <Notice :message="error"/>
 <div class="two-col">
  <section>
   <label>校准记录
    <select v-model="selected"><option value="" disabled>选择校准批次</option>
     <option v-for="r in calibrations.items.value" :key="r.id" :value="r.id">{{r.name}} · {{r.status==='completed'?'成功':'拒绝'}}</option>
    </select>
   </label>
   <EmptyState v-if="!current" text="还没有校准记录。在右侧导入实测观测后开始。"/>
   <template v-else>
    <h2>{{current.name}}</h2>
    <p class="method-note">{{current.description}}</p>
    <p><StatusPill :status="current.status"/>
     <small style="margin-left:12px">输入SHA256 <code>{{current.input_sha256.slice(0,16)}}…</code></small>
    </p>

    <template v-if="current.status==='rejected'">
     <div class="notice" role="alert"><b>整批拒绝：{{current.reject_reason}}</b><br>{{current.reject_detail}}<br>未创建任何新版代理，源模型与既有研究、归档不受影响。</div>
    </template>

    <template v-else>
     <div class="budget-strip">
      <div><small>原始观测 / 合并工况</small><strong>{{current.diagnostics.observation_count}} / {{current.diagnostics.condition_count}}</strong><span>重复测量按权重合并为单一工况</span></div>
      <div><small>参数数 / 有效秩</small><strong>{{current.diagnostics.param_count}} / {{current.diagnostics.effective_rank}}</strong><span>秩不足即整批拒绝</span></div>
      <div><small>加权 R²</small><strong>{{num(current.diagnostics.weighted_r_squared,5)}}</strong><span>合并工况口径</span></div>
     </div>

     <h3 class="table-heading">系数（物理坐标原值）</h3>
     <div class="table-wrap"><table>
      <thead><tr><th>项</th><th>拟合系数</th><th>标准误</th></tr></thead>
      <tbody>
       <tr v-for="(c,i) in current.diagnostics.column_names" :key="i">
        <td><b>{{c}}</b></td><td>{{num(current.diagnostics.coefficients[i],6)}}</td>
        <td>{{num(current.diagnostics.coefficient_standard_errors?.[i],6)}}</td>
       </tr>
      </tbody>
     </table></div>

     <h3 class="table-heading">残差平方和对账（加权 WSSR）</h3>
     <div class="budget-strip">
      <div><small>原始观测 raw_wssr</small><strong>{{scientific(current.diagnostics.raw_wssr)}}</strong><span>逐条观测的加权残差平方和</span></div>
      <div><small>合并工况 merged_wssr</small><strong>{{scientific(current.diagnostics.merged_wssr)}}</strong><span>拟合只使用合并后的工况</span></div>
      <div><small>工况内 within_wssr</small><strong>{{scientific(current.diagnostics.within_wssr)}}</strong><span>重复测量离散，不参与拟合</span></div>
     </div>
     <p class="method-note">对账恒等式 raw_wssr = merged_wssr + within_wssr；对账差 = {{scientific(current.diagnostics.reconciliation_gap)}}（浮点精度内为0）。
      残差自由度 {{current.diagnostics.residual_degrees_of_freedom}}，残差标准误 {{num(current.diagnostics.residual_standard_error,5)}}。</p>

     <h3 class="table-heading">留一工况预测误差（LOCO，无重复测量泄漏）</h3>
     <p class="method-note">每次剔除整个工况及其全部重复测量后重新拟合，再预测该工况。{{current.diagnostics.loco.note}}</p>
     <div class="budget-strip" v-if="current.diagnostics.loco.complete">
      <div><small>PRESS（加权）</small><strong>{{scientific(current.diagnostics.loco.press)}}</strong><span>留一预测残差平方和</span></div>
      <div><small>LOCO RMSE</small><strong>{{num(current.diagnostics.loco.loco_rmse,4)}}</strong><span>按合并权重归一</span></div>
      <div><small>Q²</small><strong>{{num(current.diagnostics.loco.q_squared,5)}}</strong><span>1 − PRESS/总平方和，可为负</span></div>
     </div>
     <div class="notice" v-else>剔除任一工况后设计秩不足，无法给出留一预测；请增加工况数（至少参数数+1个工况）。</div>
     <div class="table-wrap"><table>
      <thead><tr><th>工况</th><th>重复数</th><th>实测(合并)</th><th>留一预测</th><th>预测误差</th><th>加权平方误差</th></tr></thead>
      <tbody>
       <tr v-for="p in current.diagnostics.loco.predictions" :key="p.condition_id">
        <td><b>{{p.condition_id}}</b></td><td>{{p.replicate_count}}</td>
        <td>{{num(p.held_out_response,4)}}</td><td>{{num(p.prediction,4)}}</td>
        <td>{{num(p.prediction_error,4)}}</td><td>{{p.weighted_squared_error===null?'—':scientific(p.weighted_squared_error)}}</td>
       </tr>
      </tbody>
     </table></div>

     <details class="model-details">
      <summary>数值诊断：奇异值与列缩放</summary>
      <p class="method-note">列对角缩放仅用于稳定SVD求解，报告系数已还原为物理坐标。缩放后设计条件数由最大/最小奇异值决定，跨度悬殊时仍保持有界。</p>
      <div class="table-wrap"><table>
       <thead><tr><th>列</th><th>缩放尺度</th><th>—</th></tr></thead>
       <tbody><tr v-for="(s,i) in current.diagnostics.column_scales" :key="i"><td>{{current.diagnostics.column_names[i]}}</td><td>{{scientific(s)}}</td><td></td></tr></tbody>
      </table></div>
      <p class="method-note">奇异值：<code v-for="(s,i) in current.diagnostics.singular_values" :key="i">{{scientific(s)}} </code><br>秩阈值 {{scientific(current.diagnostics.rank_threshold)}}。</p>
     </details>

     <form v-if="canWrite()" class="editor-panel" style="margin-top:24px" @submit.prevent="buildStudy">
      <h2>用新版代理建立研究</h2>
      <p class="method-note" style="margin-top:0">将复制所选源空间的物理范围到新版代理，再创建Morris/Sobol研究；源空间与既有研究不变。</p>
      <label>源因子空间（复制范围）
       <select v-model="sourceSpaceId"><option v-for="s in modelSpaces" :key="s.id" :value="s.id">{{s.name}}</option></select>
      </label>
      <div class="form-pair">
       <label>新研究名称<input v-model="studyName" required minlength="2"></label>
       <label>新因子空间名称<input v-model="spaceName" required minlength="2"></label>
      </div>
      <div class="form-pair">
       <label>Morris轨迹r<input type="number" v-model.number="trajectories" min="2" max="128" required></label>
       <label>偶数网格p<input type="number" v-model.number="levels" min="2" max="20" step="2" required></label>
      </div>
      <div class="form-pair">
       <label>Sobol m<input type="number" v-model.number="power" min="2" max="16" required></label>
       <label>seed<input type="number" v-model.number="seed" min="0" max="4294967295" required></label>
      </div>
      <Notice :message="studyError"/>
      <button :disabled="studyBusy||!sourceSpaceId">复制范围并建立研究</button>
     </form>
    </template>
   </template>
  </section>

  <form v-if="canWrite()" class="editor-panel" @submit.prevent="submit">
   <h2>导入实测观测</h2>
   <label>校准名称<input v-model="name" required minlength="2"></label>
   <label>源代理模型（结构基准，不被修改）
    <select v-model="modelId"><option v-for="m in models.items.value" :key="m.id" :value="m.id">{{m.name}}</option></select>
   </label>
   <label>观测CSV
    <textarea v-model="observations" rows="10" required></textarea>
   </label>
   <p class="method-note" style="margin-top:0">
    列为 <code>condition_id,{{factorIds.join(',')}},response,weight</code>。同一 <code>condition_id</code> 的行必须因子点一致，按权重合并为加权均值；权重须为正有限数，否则整批拒绝。需要至少 参数数+1 个不同工况，当前模型参数数 = {{1+2*(sourceModel?.factors?.length||0)+(sourceModel?.interactions?.length||0)}}。
   </p>
   <label>校准说明<input v-model="description"></label>
   <button :disabled="busy">校验拟合并生成新版代理</button>
  </form>
 </div>
</template>
