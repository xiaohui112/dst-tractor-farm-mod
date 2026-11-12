-- Extracted from local DST r762172 scripts/stategraphs/SGwilson.lua mount.timeline.
-- Test-only native sound callbacks; not included in the Mod.
return {
            --Heavy lifting
            TimeEvent(12 * FRAMES, function(inst)
                if inst.sg.statemem.heavy then
                    inst.SoundEmitter:PlaySound("dontstarve/beefalo/saddle/dismount")
                end
            end),
            TimeEvent(14 * FRAMES, function(inst)
                if inst.sg.statemem.ridingwoby then
                    inst.SoundEmitter:PlaySound("dontstarve/characters/walter/woby/big/bark")
                elseif not inst.sg.statemem.heavy then
                    inst.SoundEmitter:PlaySound("dontstarve/beefalo/grunt")
                end

            end),
            TimeEvent(38 * FRAMES, function(inst)
                if inst.sg.statemem.heavy then
                    inst.SoundEmitter:PlaySound("dontstarve/movement/bodyfall_dirt")
                end
            end),

            --Normal
            TimeEvent(20 * FRAMES, function(inst)
                if not inst.sg.statemem.heavy then
                    inst.SoundEmitter:PlaySound("dontstarve/beefalo/saddle/dismount")
                    inst.SoundEmitter:PlaySound("dontstarve/movement/bodyfall_dirt")
                end
            end),
        }
