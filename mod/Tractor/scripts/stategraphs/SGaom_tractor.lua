-- 原版 Rider:ActualDismount 会调用 mount.sg:GoToState("idle")。
-- 角色继续使用原版 SGwilson；这里仅负责底盘恢复待机动画。
return StateGraph("aom_tractor", {
	State{
		name = "idle",
		tags = { "idle" },
		onenter = function(inst)
			inst.AnimState:PlayAnimation(inst._destroyed and "death" or "idle", not inst._destroyed)
		end,
	},
}, {}, "idle")
