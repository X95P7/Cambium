/*******************************************************************************
 * This file is part of Minebot.
 *
 * Minebot is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Minebot is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Minebot.  If not, see <http://www.gnu.org/licenses/>.
 *******************************************************************************/
package net.famzangl.minecraft.minebot.ai.task.move;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.ItemFilter;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSets;
import net.famzangl.minecraft.minebot.ai.path.world.WorldWithDelta;
import net.famzangl.minecraft.minebot.ai.task.TaskOperations;
import net.famzangl.minecraft.minebot.ai.task.error.PositionTaskError;
import net.famzangl.minecraft.minebot.ai.task.place.JumpingPlaceBlockAtFloorTask;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;

/**
 * Move upwards by digging one block up and then jumping while placing a block
 * below the feet.
 * 
 * @author michael
 *
 */
public class UpwardsMoveTask extends JumpingPlaceBlockAtFloorTask {
	//private static final BlockSet DESTRUCTABLE_GROUND = BlockSets.SAFE_GROUND.intersectWith(BlockSets.AIR.invert());

	private boolean obsidianMining;

	/**
	 * FIXME: Find a nice, central place for digging times.
	 */
	private static final BlockSet hardBlocks = new BlockSet(
			Blocks.field_150343_Z);

	public UpwardsMoveTask(BlockPos pos, ItemFilter filter) {
		super(pos, filter);
	}

	@Override
	public void runTick(AIHelper h, TaskOperations o) {
		if (!BlockSets.HEAD_CAN_WALK_TRHOUGH.isAt(h.getWorld(), pos.func_177982_a(0, 1, 0))) {
			if (!h.isStandingOn(pos.func_177982_a(0, -1, 0))) {
				o.desync(new PositionTaskError(pos.func_177982_a(0, -1, 0)));
			}
			if (hardBlocks.contains(h.getBlock(pos.func_177982_a(0, 1, 0)))) {
				obsidianMining = true;
			}
			h.faceAndDestroy(pos.func_177982_a(0, 1, 0));
		} else if (!BlockSets.AIR.isAt(h.getWorld(), pos.func_177982_a(0, -1, 0))) {
			h.faceAndDestroy(pos.func_177982_a(0, -1, 0));
		} else {
			super.runTick(h, o);
		}
	}

//	@Override
//	public int getGameTickTimeout(AIHelper helper) {
//		return super.getGameTickTimeout(helper)
//				+ (obsidianMining ? HorizontalMoveTask.OBSIDIAN_TIME : 0);
//	}

	@Override
	public String toString() {
		return "UpwardsMoveTask [pos=" + pos + "]";
	}
	
	@Override
	public boolean applyToDelta(WorldWithDelta world) {
		// we always set cobblestone... TODO: set other material.
		
		world.setBlock(getPlaceAtPos(), Blocks.field_150347_e);
		world.setBlock(pos, Blocks.field_150350_a);
		world.setBlock(pos.func_177982_a(0, 1, 0), Blocks.field_150350_a);
		
		return super.applyToDelta(world);
	}

}
