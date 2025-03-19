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
import net.famzangl.minecraft.minebot.ai.strategy.TaskStrategy;
import net.famzangl.minecraft.minebot.ai.task.inventory.SwapInventoryTask;

/**
 * Swap inventory slots
 * 
 * @author Xylim
 *
 */
public class SwapInventoryStrategy extends TaskStrategy {

    public SwapInventoryStrategy(int hotbarSlot, int inventorySlot){
        AIChatController.addChatLine("Calling swap task");
			addTask(new SwapInventoryTask(hotbarSlot, inventorySlot));
    }

	@Override
	public void searchTasks(AIHelper helper) {
        //no need
	}

	@Override
	public String getDescription(AIHelper helper) {
		return "Swap inventory slots";
	}
}
