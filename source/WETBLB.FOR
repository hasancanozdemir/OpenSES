      SUBROUTINE WETBLB( TDB, W, TWB )                                  
C    THIS SUBROUTINE CONVERTS DRY BULB TEMPERATURE AND SPECIFIC HUMIDITY
C             INTO WETBULB TEMPERATURE.  THE ACCURACY OF THE CONVERSION 
C             IS APPROXIMATELY WITHIN ONE HALF OF ONE DEGREE OF THE     
C             ACTUAL VALUE.                                             
C                                                                       
C     TDB = DRY BULB TEMPERATURE (DEG F)                                
C     W = SPECIFIC HUMIDITY (LB OF WATER/LB OF DRY AIR)                 
C     TWB = WET BULB TEMPERATURE (DEG F)                                
C                                                                       
C                                                                       
C     INCLUDE                                  ( DATE: 15 AUGUST 1997 ) 
C     
      INCLUDE  'DSHARE'                                                 
C                                                                        
C                                                                        
C                                                                        
C                                                                        
        IF (INPUT_UNITS .EQ. UNIT_SI) THEN
        TDBF = TDB*9.0/5.0 + 32.0
        PAMB_INHG = PAMB*0.2952998751
        ELSE
        TDBF = TDB
        PAMB_INHG = PAMB
        END IF
        H = .24 * TDBF + (1061. + .444 * TDBF ) * W                      
      Y = LOG(H)                                                       
      IF (H - 11.758 ) 30,20,20                                         
   20 TWB = 30.9185 - 39.682 * Y + 20.5841 * Y**2 - 1.758 * Y**3        
      GO TO 100                                                         
   30 TWB = .604 + 3.4841 * Y + 1.3601 * Y**2 + .9731 * Y**3            
  100 WBDELT = -(-.48*PAMB_INHG + 36.71)*(1. - PAMB_INHG/SAINHG)
        CORR = (.404 + .00276*PAMB_INHG)*H/26.96 - .00425*PAMB_INHG + .385
      TWB = TWB + WBDELT * CORR                                         
        IF( TWB - TDBF ) 120,120,110                                     
  110 TWB = TDBF                                                       
  120 IF (INPUT_UNITS .EQ. UNIT_SI) TWB = (TWB - 32.0)*5.0/9.0
        RETURN                                                           
      END                                                               
