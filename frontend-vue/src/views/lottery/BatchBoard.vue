<script setup lang="ts">
// 批次网格(开一批玩法):背面卡 → 点卡挂刮 → 结算后翻面 hit/miss;顶部小计 + 全批战报。
// 数据源:后端 /lottery/batch/{id} 聚合(批次持久化在服务端,刷新经 active_batch 续挂)。
// 「开批即定局」——每张输赢开批瞬间已定,先刮后刮、刮哪张都一样(战报文案同原版)。
import { computed } from 'vue'
import type { BatchSummary } from '@/api/types'
import { fmtPrize } from '@/constants/lottery'

const props = defineProps<{
  summary: BatchSummary
}>()

const emit = defineEmits<{
  /** 点一张未结算的卡,父层取票挂刮 */
  pick: [ticketId: number]
}>()

const done = computed(() => props.summary.remaining === 0)
const settledRatio = computed(() =>
  props.summary.size ? Math.round((props.summary.settled / props.summary.size) * 100) : 0,
)
</script>

<template>
  <div class="batch">
    <div class="batch-head">
      <div class="batch-title">🎴 本批 {{ summary.size }} 张</div>
      <div class="batch-sub">开批即定局——每张的输赢在开批瞬间已按当前概率抽好,先刮后刮、刮哪张都一样</div>
      <div class="batch-stats">
        已核对 <b>{{ summary.settled }}</b
        >/{{ summary.size }} · 中奖 <b>{{ summary.hit_count }}</b> 张 · 中奖合计
        <b class="pos">¥{{ fmtPrize(summary.total_prize) }}</b> · 最大单张
        <b>{{ summary.best_prize > 0 ? `¥${fmtPrize(summary.best_prize)}` : '—' }}</b>
      </div>
      <div class="batch-progress"><i :style="{ width: `${settledRatio}%` }"></i></div>
    </div>
    <p v-if="done" class="batch-note">
      本批战报:{{ summary.hit_count }} 张中奖,合计 ¥{{ fmtPrize(summary.total_prize)
      }}{{ summary.total_prize === 0 ? '——下次学习赚够次数再来开一批吧' : ',已全部入账 🎉' }}
    </p>
    <div class="batch-grid">
      <template v-for="t in summary.tickets" :key="t.id">
        <button v-if="!t.settled" class="bcard" @click="emit('pick', t.id)">
          <span class="bcard-no">No.{{ t.index }}</span>
          <span class="bcard-face">🎫</span>
        </button>
        <div v-else class="bcard done" :class="t.prize > 0 ? 'hit' : 'miss'">
          <span class="bcard-no">No.{{ t.index }}</span>
          <span class="bcard-prize">{{ t.prize > 0 ? `¥${fmtPrize(t.prize)}` : '未中' }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.batch-head {
  text-align: center;
  margin-bottom: 12px;
}
.batch-title {
  font-size: 18px;
  font-weight: 700;
}
.batch-sub {
  font-size: 12px;
  color: #999;
  margin: 4px 0;
}
.batch-stats {
  font-size: 13px;
  color: #666;
}
.batch-stats b {
  color: #333;
}
.batch-stats .pos {
  color: #c23a28;
}
.batch-progress {
  height: 4px;
  background: #f0e6d8;
  border-radius: 2px;
  margin: 8px auto 0;
  max-width: 420px;
  overflow: hidden;
}
.batch-progress i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #f5c451, #c23a28);
  transition: width 0.3s;
}
.batch-note {
  text-align: center;
  font-size: 13px;
  color: #7a1610;
  background: rgba(245, 196, 81, 0.15);
  border-radius: 8px;
  padding: 8px 12px;
}
.batch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(84px, 1fr));
  gap: 8px;
  max-width: 640px;
  margin: 0 auto;
}
.bcard {
  aspect-ratio: 5 / 7;
  border-radius: 10px;
  border: 1px solid #e5d9c5;
  background: linear-gradient(160deg, #fff8ec, #f3e6cf);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  font-family: inherit;
  transition:
    transform 0.15s,
    box-shadow 0.15s;
}
.bcard:not(.done):hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(122, 22, 16, 0.18);
}
.bcard.done {
  cursor: default;
}
.bcard-no {
  font-size: 11px;
  color: #a08a5f;
}
.bcard-face {
  font-size: 26px;
}
.bcard-prize {
  font-size: 13px;
  font-weight: 900;
}
.bcard.done.hit {
  background: radial-gradient(circle at 50% 30%, #fff3cf, #ffe08a);
  border-color: #f5c451;
}
.bcard.done.hit .bcard-prize {
  color: #c23a28;
}
.bcard.done.miss {
  background: #f5f3ef;
  border-color: #e0dcd4;
}
.bcard.done.miss .bcard-prize {
  color: #b3ab9d;
}
</style>
