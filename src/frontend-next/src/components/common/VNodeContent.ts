import type { PropType, VNode } from 'vue'
import { defineComponent } from 'vue'

/** 将 render 函数返回的 VNode 渲染到模板中 */
const VNodeContent = defineComponent({
  props: {
    node: {
      type: [Object, String, Number] as PropType<VNode | string | number | null>,
      default: null,
    },
  },
  setup(props) {
    return () => props.node
  },
})

export default VNodeContent
