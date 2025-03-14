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
package net.famzangl.minecraft.minebot.ai.commands.cambium;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AICommand;
import net.famzangl.minecraft.minebot.ai.command.AICommandInvocation;
import net.famzangl.minecraft.minebot.ai.command.AICommandParameter;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.command.ParameterType;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.strategy.cambium.MovementStrategy;


@AICommand(helpText = "Control all movement of the bot", name = "cambium")
public class CommandMovement {
	@AICommandInvocation()
	public static AIStrategy run(
			AIHelper helper,
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "move", description = "") String nameArg,
			@AICommandParameter(type = ParameterType.NUMBER, fixedName = "move", description = "") double x,
			@AICommandParameter(type = ParameterType.NUMBER, fixedName = "move", description = "") double z,
			@AICommandParameter(type = ParameterType.NUMBER, fixedName = "move", description = "") int jump,
			@AICommandParameter(type = ParameterType.NUMBER, fixedName = "move", description = "") double changeYaw,
			@AICommandParameter(type = ParameterType.NUMBER, fixedName = "move", description = "") double changePitch) {
				boolean trueJump = false;
				if(jump == 1){
					trueJump = true;
				}
                
        AIChatController.addChatLine("cambium bot is moving message");
		
		return new MovementStrategy(x, z, trueJump, changeYaw, changePitch, helper);
	}
}
