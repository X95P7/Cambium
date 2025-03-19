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

//cambium
import net.famzangl.minecraft.minebot.ai.strategy.cambium.SwapInventoryStrategy;;

//Update help command
@AICommand(helpText = "Swap inventory slot i with hotbar slot j", name = "cambium")

// --Command function--
// Swaps 2 inventory slots, one must be in the hotbar

//Change classs to file name
public class CommandSwapInventory {
    @AICommandInvocation()
    public static AIStrategy run(
            AIHelper helper,
            @AICommandParameter(type = ParameterType.FIXED, fixedName = "swap", description = "") String nameArg,
            @AICommandParameter(type = ParameterType.NUMBER, description = "hotbar") int hotbarSlot,
            @AICommandParameter(type = ParameterType.NUMBER, description = "inventory") int inventorySlot) {

        // Ensure slots are within valid ranges
        hotbarSlot = Math.max(0, Math.min(hotbarSlot, 8)) + 36; // Hotbar slots range: 0-8 adn then mapped
        inventorySlot = Math.max(0, Math.min(inventorySlot, 35)); // Inventory slots range: 9-35
		inventorySlot = ((inventorySlot + 27) % 36) + 9; 
		
		AIChatController.addChatLine("Calling swap stratgey");
        return new SwapInventoryStrategy(hotbarSlot, inventorySlot);
    }
}


 
