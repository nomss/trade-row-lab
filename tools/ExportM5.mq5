//+------------------------------------------------------------------+
//| ExportM5.mq5 — BlindLab: dump full M5 history per symbol to CSV  |
//| Output: MQL5\Files\BlindLab\export\SYMBOL_M5.csv                 |
//| No trading functions. Run once; ~10-30s for all symbols.         |
//+------------------------------------------------------------------+
#property copyright "BlindLab"
#property version   "1.00"
#property script_show_inputs

input string InpSymbols = "NASUSD,U30USD,SPXUSD,XAUUSD,USOUSD,EURUSD,GBPUSD,USDCAD,USDJPY,AUDUSD";

void OnStart()
  {
   string parts[];
   int n=StringSplit(InpSymbols,',',parts);
   int done=0;
   for(int i=0;i<n;i++)
     {
      string s=parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      if(s=="" || !SymbolSelect(s,true)) continue;
      int total=Bars(s,PERIOD_M5);
      if(total<1000){ Print("BlindLab export: no history for ",s); continue; }
      MqlRates r[];
      int got=CopyRates(s,PERIOD_M5,0,total,r);
      if(got<1000){ Print("BlindLab export: CopyRates failed for ",s," got=",got); continue; }
      int h=FileOpen("BlindLab\\export\\"+s+"_M5.csv",FILE_WRITE|FILE_TXT|FILE_ANSI);
      if(h==INVALID_HANDLE){ Print("BlindLab export: cannot open file for ",s); continue; }
      int digits=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
      for(int j=got-1;j>=0;j--)      // oldest first
         FileWriteString(h,(string)(long)r[j].time+","+
            DoubleToString(r[j].open,digits)+","+DoubleToString(r[j].high,digits)+","+
            DoubleToString(r[j].low,digits)+","+DoubleToString(r[j].close,digits)+"\n");
      FileClose(h);
      done++;
      Print("BlindLab export: ",s," -> ",got," bars");
     }
   Alert("BlindLab export complete: ",done," symbols written to Files\\BlindLab\\export\\");
  }
//+------------------------------------------------------------------+
