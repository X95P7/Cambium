

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

//client
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;

/**
 * Use an item
 * 
 * @author Xylim
 *
 */
public class MovementStrategy extends AIStrategy {
  private boolean jump;
  private double x;
  private double z;

    //need: face, walk, jump, sprint
    public MovementStrategy(double x, double z, boolean jump, double yawChange, double pitchChange, AIHelper helper){

        
        helper.faceDirection((float) yawChange, (float) pitchChange);
        this.jump = jump;
        this.x = x;
        this.z = z;
        helper.walkTowards(x, z, jump, false);
    }

    public String getDescription(AIHelper helper) {
		return "Using item!" + getClass().getSimpleName();
	}

    @Override
	protected TickResult onGameTick(AIHelper helper) {
    final double d0 = x - helper.getMinecraft().thePlayer.posX;
		final double d1 = z - helper.getMinecraft().thePlayer.posZ;
    if(Math.pow(d0,2) + Math.pow(d1,2) < 0.15){
        return TickResult.ABORT;
    }

    helper.walkTowards(x, z, jump, false);
        return TickResult.TICK_HANDLED;
	}

}


        

