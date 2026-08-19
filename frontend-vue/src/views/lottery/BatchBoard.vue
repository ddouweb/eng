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
        <div v-else class="bcard done" :class="{ hit: t.prize > 0 }">
          <span class="bcard-no">No.{{ t.index }}</span>
          <span class="bcard-prize">{{ t.prize > 0 ? `¥${fmtPrize(t.prize)}` : '未中' }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* 逐值照抄原版 css/style.css「抽卡批次面板」段——深色舞台底上金字红卡 */
.batch-head {
  text-align: center;
  margin-bottom: 14px;
}
.batch-title {
  font-size: 18px;
  font-weight: 900;
  color: #f5c451;
}
.batch-sub {
  font-size: 12px;
  color: #cdb98d;
  margin-top: 4px;
}
.batch-stats {
  font-size: 13px;
  color: #e8d5a3;
  margin-top: 8px;
}
.batch-stats b {
  color: #ffe9b0;
}
.batch-stats .pos {
  color: #7bd88f;
}
.batch-note {
  text-align: center;
  font-size: 12px;
  color: #b9a677;
  margin: 0 0 12px;
  line-height: 1.7;
}
.batch-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(245, 196, 81, 0.3);
  border-radius: 14px;
  padding: 12px;
}
/* 一张卡：未刮 = 竖版小彩票（红金），已刮 = 翻开的结果（原版同款） */
.bcard {
  aspect-ratio: 3 / 4;
  border: none;
  border-radius: 10px;
  font-family: inherit;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #ffe9b0;
  background: linear-gradient(160deg, #d8452f, #8e1c1c);
  box-shadow:
    inset 0 0 0 1.5px rgba(255, 220, 150, 0.55),
    0 3px 8px rgba(0, 0, 0, 0.4);
  transition: transform 0.12s;
}
.bcard:hover {
  transform: translateY(-2px) scale(1.04);
}
.bcard:active {
  transform: scale(0.97);
}
.bcard .bcard-no {
  font-size: 10px;
  color: rgba(255, 233, 176, 0.75);
}
.bcard .bcard-face {
  font-size: 22px;
}
.bcard.done {
  cursor: default;
  background: rgba(255, 255, 255, 0.06);
  box-shadow: inset 0 0 0 1.5px rgba(245, 196, 81, 0.25);
  transform: none;
}
.bcard.done .bcard-no {
  color: #9d8a63;
}
.bcard.done .bcard-prize {
  font-size: 12px;
  font-weight: 800;
  color: #9d8a63;
}
.bcard.done.hit {
  box-shadow: inset 0 0 0 1.5px rgba(245, 196, 81, 0.7);
}
.bcard.done.hit .bcard-prize {
  color: #f5c451;
}
</style>
