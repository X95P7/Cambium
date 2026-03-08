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
package net.famzangl.minecraft.minebot.build.reverse;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.PrintStream;

import net.famzangl.minecraft.minebot.MinebotMod;
import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.path.world.Pos;
import net.famzangl.minecraft.minebot.build.reverse.factories.BuildTaskFactories;
import net.minecraft.block.Block;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumFacing;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.Marker;
import org.apache.logging.log4j.MarkerManager;

/**
 * This does the reverse of building: it creates a build script from a given
 * area.
 * 
 * @author michael
 *
 */
public class BuildReverser {
	private static final Marker MARKER_RECONSTRUCT = MarkerManager
			.getMarker("reconstruct");
	private static final Logger LOGGER = LogManager.getLogger(BuildReverser.class);
	private final AIHelper helper;
	private final BlockPos minPos;
	private final BlockPos maxPos;
	private final ReverseBuildField field;
	private File outFile;
	private PrintStream out;
	private int missingBlocks;

	public BuildReverser(AIHelper helper, File outFile) {
		this(helper, Pos.minPos(helper.getPos1(), helper.getPos2()), Pos
				.maxPos(helper.getPos1(), helper.getPos2()), outFile);
	}

	public BuildReverser(AIHelper helper, BlockPos minPos, BlockPos maxPos,
			File outFile) {
		this.helper = helper;
		this.minPos = minPos;
		this.maxPos = maxPos;
		field = new ReverseBuildField(maxPos.func_177958_n() - minPos.func_177958_n() + 1,
				maxPos.func_177956_o() - minPos.func_177956_o() + 1, maxPos.func_177952_p()
						- minPos.func_177952_p() + 1);
		this.outFile = outFile;
	}

	public void run() {
		try {
			if (outFile == null || "-".equals(outFile)) {
				this.outFile = null;
				this.out = System.out;
				LOGGER.info(MARKER_RECONSTRUCT, "Printing reverse build output.");
			} else {
				this.out = new PrintStream(outFile);
				LOGGER.info(MARKER_RECONSTRUCT, "Writing reverse build output to " + outFile);
			}
			out.println("# Minebot reverse build script "
					+ MinebotMod.getVersion());
			out.println("# Pos1: " + minPos);
			out.println("# Pos2: " + maxPos);
			out.println("");
			out.println("/minebuild reset");
			out.println("");
			for (int y = minPos.func_177956_o(); y <= maxPos.func_177956_o(); y++) {
				LOGGER.trace(MARKER_RECONSTRUCT, "Start layer at y=" + y);
				out.println("# Layer " + (y - minPos.func_177956_o()));
				for (int x = minPos.func_177958_n(); x <= maxPos.func_177958_n(); x++) {
					final boolean row2 = (x - minPos.func_177958_n() & 1) == 1;
					addRow(new BlockPos(x, y, row2 ? maxPos.func_177952_p()
							: minPos.func_177952_p()), row2 ? EnumFacing.NORTH
							: EnumFacing.SOUTH, maxPos.func_177952_p() - minPos.func_177952_p()
							+ 1);
				}
				out.println("");
			}
			out.println("#/minebuild build");

			if (missingBlocks > 0) {
				AIChatController.addChatLine("Could not convert "
						+ missingBlocks + "blocks. They will be missing.");
			}
			AIChatController.addChatLine("Output written to: "
					+ (this.outFile == null ? "Stdout" : this.outFile
							.getAbsolutePath()));
		} catch (final FileNotFoundException e) {
			AIChatController.addChatLine("File/dir does not exist: " + outFile);
		} catch (final IOException e) {
			AIChatController.addChatLine("IO-Error for: " + outFile);
		} finally {
			if (out != null) {
				out.close();
				out = null;
			}
		}
	}

	public void addRow(BlockPos start, EnumFacing direction, int length) {
		for (int i = 0; i < length; i++) {
			addBuildPlace(start.func_177967_a(direction, i));
		}
	}

	private void addBuildPlace(BlockPos pos) {
		BlockPos localPos = pos.func_177973_b(minPos);
		LOGGER.trace(MARKER_RECONSTRUCT, "Reconstructing block at " + pos);

		final Block b = helper.getBlock(pos);
		if (b != Blocks.field_150350_a) {
			try {
				final TaskDescription taskString = BuildTaskFactories.getTaskFor(helper.getWorld(), pos) ;
				LOGGER.trace(MARKER_RECONSTRUCT, "Resulting description: " + taskString);
				field.setBlockAt(localPos, b, taskString);
				out.println("/minebuild schedule ~" + localPos.func_177958_n() + " ~"
						+ localPos.func_177956_o() + " ~" + localPos.func_177952_p() + " "
						+ taskString.getCommandArgs());
			} catch (final UnsupportedBlockException e) {
				out.println("# Missing: ~" + localPos.func_177958_n() + " ~"
						+ localPos.func_177956_o() + " ~" + localPos.func_177952_p() + " "
						+ b.func_149732_F());
				LOGGER.warn(MARKER_RECONSTRUCT, "Error: " + e.getMessage());
				missingBlocks++;
			}
		}
	}
}
