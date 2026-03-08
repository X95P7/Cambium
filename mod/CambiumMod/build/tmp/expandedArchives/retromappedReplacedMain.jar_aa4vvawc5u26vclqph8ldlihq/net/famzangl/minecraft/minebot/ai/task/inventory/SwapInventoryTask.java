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
package net.famzangl.minecraft.minebot.ai.task.inventory;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.task.AITask;
import net.famzangl.minecraft.minebot.ai.task.SkipWhenSearchingPrefetch;
import net.famzangl.minecraft.minebot.ai.task.TaskOperations;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraft.client.gui.inventory.GuiInventory;
import net.minecraft.client.multiplayer.PlayerControllerMP;


/**
 * Gets the item on the hotbar out of the inventory. Currently only uses slot 5.
 * 
 * @author michael
 * 
 */
@SkipWhenSearchingPrefetch
public class SwapInventoryTask extends AITask {
	private int hotbarSlot;
	private int InventorySlot;
	private boolean done;

	public SwapInventoryTask(int hotbarSlot, int InventorySlot) {
		super();
		this.hotbarSlot = hotbarSlot;
		this.InventorySlot = InventorySlot;
		done = false;
	}

	@Override
	public boolean isFinished(AIHelper h) {
		return done;
	}

	@Override
	public void runTick(AIHelper h, TaskOperations o) {
		//if gui is open
		if (h.getMinecraft().field_71462_r instanceof GuiInventory) {
			AIChatController.addChatLine("Swapping items");
			//Swap the two inventroy slots
			final GuiInventory screen = (GuiInventory) h.getMinecraft().field_71462_r;
			final PlayerControllerMP playerController = h.getMinecraft().field_71442_b;
			final int windowId = screen.field_147002_h.field_75152_c;
			final EntityPlayerSP player = h.getMinecraft().field_71439_g;
			playerController.func_78753_a(windowId, InventorySlot, 0, 0, player);
			playerController.func_78753_a(windowId, hotbarSlot, 0, 0, player);
			playerController.func_78753_a(windowId, InventorySlot, 0, 0, player);

			//close gui
				h.getMinecraft().func_147108_a(null);
				done = true;
		} else{
			//open gui screenif it isnt open 
			AIChatController.addChatLine("opening GUI Screen");
			h.getMinecraft().func_147108_a(
					new GuiInventory(h.getMinecraft().field_71439_g));
		}
	}

}
