

/*******************************************************************************
    _______      ____    ,---.    ,---. _______  .-./`)   ___    _ ,---.    ,---.        
   /   __  \   .'  __ `. |    \  /    |\  ____  \\ .-.').'   |  | ||    \  /    |        
  | ._/  \__) /   '  \  \|  ,  \/  ,  || |    \ |/ `-' \|   .|  | ||  ,  \/  ,  |        
,-./  )       |___|  /  ||  |\_   /|  || |____/ / `-'`"`.'  'L  | ||  |\_   /|  |        
\  '_ '`)        _.-`   ||  _( )_/ |  ||   _ _ '. .---. '   ( \.-.||  _( )_/ |  |        
 > (_)  )  __ .'   _    || (_ o _) |  ||  ( ' )  \|   | ' (`. _` /|| (_ o _) |  |        
(  .  .-'_/  )|  _( )_  ||  (_,_)  |  || (_{;}_) ||   | | (_ (_) _)|  (_,_)  |  |        
 `-'`-'     / \ (_ o _) /|  |      |  ||  (_,_)  /|   |  \ /  . \ /|  |      |  |        
   `\_____.'   '.(_,_).' '--'      '--'/_______.' '---'   ``-'`-'' '--'      '--'        
                                                                                         
 *******************************************************************************/
package net.famzangl.minecraft.minebot.ai.strategy.cambium;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;

import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;
//client
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;

/**
 * Use an item
 * 
 * @author Xylim
 *
 */
public class RightClickStrategy extends AIStrategy {
    private int ticks;
    private int maxTicks;
    private double often;
    GameSettings gameSettings;
    KeyBinding useItemKey;
    int originalKeyCode;

    public RightClickStrategy(int n, int tickTime, AIHelper helper){
        gameSettings = helper.getMinecraft().field_71474_y;
        useItemKey = gameSettings.field_74313_G;
        // Save the original key code (optional, if you want to restore later)
         originalKeyCode = useItemKey.func_151469_h();
        maxTicks = tickTime;

        if(n > 15){
            n = 15;
        }

        if(n < 1){
            n = 1;
        }

        if(tickTime < 4){
            tickTime = 4;
        }

        often = n * 0.05;

        // Remap the key to the temporary key code
        useItemKey.func_151462_b(501);
        KeyBinding.func_74508_b();
    }

    public String getDescription(AIHelper helper) {
		return "Using item!" + getClass().getSimpleName();
	}

    @Override
	protected TickResult onGameTick(AIHelper helper) {
		if (ticks == maxTicks) {
            KeyBinding.func_74510_a(501, false);
            // Optionally restore the original key code (if desired)
            useItemKey.func_151462_b(originalKeyCode);
            KeyBinding.func_74508_b();
			return TickResult.ABORT;
		} else {
            ticks++;
            double random = (Math.random() - 0.5) / 10;
            double odds = Math.random();
            if(often + random >= odds){
                // Simulate press of that key
                KeyBinding.func_74510_a(501, true);
                KeyBinding.func_74507_a(501);
            }
			return TickResult.TICK_HANDLED;
		}
	}

}


        
