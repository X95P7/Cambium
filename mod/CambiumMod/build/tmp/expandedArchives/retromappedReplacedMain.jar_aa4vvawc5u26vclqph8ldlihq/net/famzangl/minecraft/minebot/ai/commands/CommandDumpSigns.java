package net.famzangl.minecraft.minebot.ai.commands;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.PrintStream;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Calendar;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AIChatController;
import net.famzangl.minecraft.minebot.ai.command.AICommand;
import net.famzangl.minecraft.minebot.ai.command.AICommandInvocation;
import net.famzangl.minecraft.minebot.ai.command.AICommandParameter;
import net.famzangl.minecraft.minebot.ai.command.ParameterType;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.strategy.RunOnceStrategy;
import net.famzangl.minecraft.minebot.settings.MinebotSettings;
import net.minecraft.block.BlockSign;
import net.minecraft.init.Blocks;
import net.minecraft.tileentity.TileEntity;
import net.minecraft.tileentity.TileEntitySign;
import net.minecraft.util.BlockPos;
import net.minecraft.util.IChatComponent;

@AICommand(helpText = "Dump all signs to a text file.", name = "minebot")
public class CommandDumpSigns {
	private static final BlockSet SIGNS = new BlockSet(Blocks.field_150472_an, Blocks.field_150444_as);
	@AICommandInvocation()
	public static AIStrategy run(
			AIHelper helper,
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "dump", description = "") String nameArg,
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "signs", description = "") String nameArg2,
			@AICommandParameter(type = ParameterType.NUMBER, description = "distance", optional = true) Integer distanceArg) {
		final int distance = distanceArg == null ? 100 : distanceArg;
		return new RunOnceStrategy() {
			@Override
			protected void singleRun(AIHelper helper) {
				final File dir = MinebotSettings.getDataDirFile("dumps");
				dir.mkdirs();
				final DateFormat df = new SimpleDateFormat(
						"yyyy-MM-dd-HH-mm-ss");
				final String date = df.format(Calendar.getInstance()
						.getTime());

				final File file = new File(dir, date + ".signdump.txt");
				dumpSignsTo(helper, file, distance);
			}

			private void dumpSignsTo(AIHelper helper, File file, int distance) {
				PrintStream out;
				try {
					out = new PrintStream(file);
					int signs = 0;

					for (BlockPos p : SIGNS.findBlocks(helper.getWorld(), helper.getPlayerPosition(), distance)) {
						dumpAtPos(helper, out, p);
						signs++;
					}
					AIChatController.addChatLine("Dumped " + signs + " signs (" + distance + " blocks radius).");
				} catch (FileNotFoundException e) {
					e.printStackTrace();
				}
			}

			private void dumpAtPos(AIHelper helper, PrintStream out, BlockPos p) {
				BlockSign block = (BlockSign) helper.getBlock(p);
				TileEntity tileentity = helper.getMinecraft().field_71441_e
						.func_175625_s(p);
				if (tileentity instanceof TileEntitySign) {
					out.print(p.func_177958_n());
					out.print("\t");
					out.print(p.func_177956_o());
					out.print("\t");
					out.print(p.func_177952_p());
					IChatComponent[] texts = ((TileEntitySign) tileentity).field_145915_a;
					for (IChatComponent t : texts) {
						out.append("\t");
						out.print(t == null ? "" : t.func_150260_c());
					}
					out.println();
				} else {
					AIChatController.addChatLine("At " + p + ": Not a sign entity.");
				}
			}
		};
	}

}
