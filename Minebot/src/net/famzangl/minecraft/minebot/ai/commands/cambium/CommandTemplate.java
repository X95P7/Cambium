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

//import command setups
import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AICommand;
import net.famzangl.minecraft.minebot.ai.command.AICommandInvocation;
import net.famzangl.minecraft.minebot.ai.command.AICommandParameter;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.command.ParameterType;

//import client info
import net.minecraft.client.gui.inventory.GuiInventory;

//import stratigies as needed
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.strategy.EatStrategy;

//General Statement: If the command is instantatious, try to fit most of the code here and only make calls from helper, using task methods make understanding code difficult

//Update help command
@AICommand(helpText = "Changes hotbar slot, inputs  0 - 8", name = "cambium")

//JAVADOC: --Command function--

//Change classs to file name (file name needs to include .java, if the import statments are white you nned to do this)
public class CommandTemplate {
	@AICommandInvocation()
	public static AIStrategy run(
			AIHelper helper,

			//Change paramters to fit command
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "hotbar", description = "") String nameArg,
            @AICommandParameter(type = ParameterType.NUMBER, description = "slot") int slot) {

			//use helper to make calls to the game
            helper.setHotbarTo(slot);

			//Give in game feedback
            AIChatController.addChatLine("switching to hotbar slot " + slot);
			
		//import stratigies to be used (example given):
		return new EatStrategy();
	}
}

//Make sure to add your command to AIChatContoller by importing it and doing: registerCommand(CommandTemplate.class); 
